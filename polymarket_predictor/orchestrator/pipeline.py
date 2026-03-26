"""MiroFish pipeline orchestrator — drives the full API lifecycle programmatically."""

import asyncio
import csv
import json
import logging
from pathlib import Path

import httpx

from polymarket_predictor.config import DEFAULT_MAX_ROUNDS, MIROFISH_API_URL

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when any step of the MiroFish pipeline fails."""


class MiroFishPipeline:
    """Drives the MiroFish API through upload, graph build, simulation, and report."""

    def __init__(self, base_url: str = MIROFISH_API_URL) -> None:
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=600.0)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        seed_file_path: Path,
        simulation_requirement: str,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> dict:
        """Run the full MiroFish pipeline: upload -> graph -> simulate -> report.

        Returns:
            The generated report dict.
        """
        logger.info("Starting pipeline with seed: %s", seed_file_path)

        # Step 1: Upload & generate ontology
        project_id = await self.upload_and_generate_ontology(seed_file_path, simulation_requirement)
        logger.info("Project created: %s", project_id)

        # Step 2: Build graph
        graph_id = await self.build_graph(project_id)
        logger.info("Graph built: %s", graph_id)

        # Step 3: Create & prepare simulation
        sim_id = await self.create_simulation(project_id)
        await self.prepare_simulation(sim_id)
        logger.info("Simulation prepared: %s", sim_id)

        # Step 3.5: Inject template agents for richer simulation dynamics
        injected = self.inject_template_agents(sim_id)
        if injected > 0:
            logger.info("Injected %d template agents into %s", injected, sim_id)

        # Step 4: Run simulation
        await self.run_simulation(sim_id, max_rounds)
        logger.info("Simulation completed: %s", sim_id)

        # Step 5: Generate report
        report = await self.generate_report(sim_id)
        logger.info("Report generated: %s", report.get("report_id", "unknown"))

        # Attach simulation_id so callers can run post-hoc analysis
        report["simulation_id"] = sim_id

        return report

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    async def upload_and_generate_ontology(self, seed_file_path: Path, requirement: str) -> str:
        """Upload a seed document and generate its ontology.

        Returns:
            The newly-created project ID.
        """
        with open(seed_file_path, "rb") as f:
            files = {"files": (seed_file_path.name, f, "text/plain")}
            data = {"simulation_requirement": requirement}
            resp = await self.client.post("/graph/ontology/generate", files=files, data=data)

        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Ontology generation failed: {result.get('error', 'unknown')}")
        return result["data"]["project_id"]

    async def build_graph(self, project_id: str) -> str:
        """Start a graph build and wait for completion.

        Returns:
            The resulting graph ID.
        """
        resp = await self.client.post("/graph/build", json={"project_id": project_id})
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Graph build start failed: {result.get('error', 'unknown')}")

        task_id = result["data"]["task_id"]

        # Poll until the build task completes
        await self._wait_for_task(f"/graph/task/{task_id}", timeout=1200)  # 20min for large graphs

        # Retrieve the graph_id from the project record
        resp = await self.client.get(f"/graph/project/{project_id}")
        resp.raise_for_status()
        project = resp.json()["data"]
        graph_id = project.get("graph_id")
        if not graph_id:
            raise PipelineError("Graph build completed but no graph_id found")
        return graph_id

    async def create_simulation(self, project_id: str) -> str:
        """Create a new simulation instance.

        Returns:
            The simulation ID.
        """
        resp = await self.client.post(
            "/simulation/create",
            json={
                "project_id": project_id,
                "enable_twitter": True,
                "enable_reddit": True,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Simulation creation failed: {result.get('error', 'unknown')}")
        return result["data"]["simulation_id"]

    async def prepare_simulation(self, simulation_id: str) -> None:
        """Prepare a simulation (generate profiles and config). Blocks until ready."""
        resp = await self.client.post("/simulation/prepare", json={"simulation_id": simulation_id})
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Simulation preparation failed: {result.get('error', 'unknown')}")

        task_id = result["data"].get("task_id")
        already_prepared = result["data"].get("already_prepared", False)

        if already_prepared:
            logger.info("Simulation %s already prepared, skipping poll", simulation_id)
        else:
            # Wait for prepare to actually start, then poll until ready
            logger.info("Waiting for prepare to complete for %s...", simulation_id)
            elapsed = 0
            timeout = 1800  # 30min for local model profile generation
            interval = 5
            while elapsed < timeout:
                await asyncio.sleep(interval)
                elapsed += interval
                # Check simulation status directly
                resp2 = await self.client.get(f"/simulation/{simulation_id}")
                if resp2.status_code == 200:
                    sim_data = resp2.json().get("data", {})
                    sim_status = sim_data.get("status", "")
                    logger.info("Simulation %s status: %s (%ds elapsed)", simulation_id, sim_status, elapsed)
                    if sim_status in ("ready", "completed"):
                        break
                    if sim_status == "failed":
                        raise PipelineError(f"Simulation prepare failed: {sim_data.get('error', 'unknown')}")
            else:
                raise PipelineError(f"Prepare timed out after {timeout}s")

    async def run_simulation(self, simulation_id: str, max_rounds: int = DEFAULT_MAX_ROUNDS) -> None:
        """Start the simulation and block until it finishes."""
        # Brief pause to let MiroFish internal state settle after prepare
        await asyncio.sleep(3)
        resp = await self.client.post(
            "/simulation/start",
            json={
                "simulation_id": simulation_id,
                "max_rounds": max_rounds,
                "force": True,  # Force start even if status isn't READY
            },
        )
        if resp.status_code >= 400:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", resp.text[:200])
            except Exception:
                err_msg = resp.text[:200]
            raise PipelineError(f"Simulation start failed ({resp.status_code}): {err_msg}")
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Simulation start failed: {result.get('error', 'unknown')}")

        # Poll run status until the simulation completes
        while True:
            await asyncio.sleep(5)
            resp = await self.client.get(f"/simulation/{simulation_id}/run-status")
            resp.raise_for_status()
            status_data = resp.json().get("data", {})

            status = status_data.get("runner_status", "") or status_data.get("status", "")
            current_round = status_data.get("twitter_current_round", 0) or status_data.get(
                "reddit_current_round", 0
            )
            progress = status_data.get("progress_percent", 0)
            logger.info("Simulation round %s/%s - status: %s (%s%%)", current_round, max_rounds, status, progress)

            if status in ("completed", "stopped"):
                break
            if status in ("error", "failed"):
                raise PipelineError(f"Simulation failed: {status_data.get('error', 'unknown')}")

    async def generate_report(self, simulation_id: str) -> dict:
        """Generate a report and block until it is ready.

        Returns:
            The full report dict.
        """
        resp = await self.client.post("/report/generate", json={"simulation_id": simulation_id})
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise PipelineError(f"Report generation failed: {result.get('error', 'unknown')}")

        report_id = result["data"]["report_id"]
        task_id = result["data"].get("task_id")

        # Poll until the report is complete
        while True:
            await asyncio.sleep(3)
            poll_body = {"simulation_id": simulation_id}
            if task_id:
                poll_body["task_id"] = task_id
            resp = await self.client.post("/report/generate/status", json=poll_body)
            resp.raise_for_status()
            status_data = resp.json().get("data", {})

            status = status_data.get("status", "")
            progress = status_data.get("progress", 0)
            logger.info("Report progress: %s%% - %s", progress, status_data.get("message", ""))

            if status == "completed":
                break
            if status == "failed":
                raise PipelineError(f"Report generation failed: {status_data.get('error', 'unknown')}")

        # Fetch the full report
        resp = await self.client.get(f"/report/{report_id}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    # ------------------------------------------------------------------
    # Template agent injection
    # ------------------------------------------------------------------

    # Resolve the MiroFish simulation data directory relative to this file.
    _SIM_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "MiroFish" / "backend" / "uploads" / "simulations"

    def inject_template_agents(self, simulation_id: str, max_templates: int = 25) -> int:
        """Inject template market-participant agents into an already-prepared simulation.

        This adds universal archetypes (retail traders, whales, contrarians, etc.)
        on top of the graph-derived organic agents, pushing agent count from ~10-20
        to ~40-50 without requiring richer seed documents.

        The method modifies three on-disk artefacts:
          1. simulation_config.json  — appends agent_configs entries
          2. reddit_profiles.json    — appends matching profile records
          3. twitter_profiles.csv    — appends matching profile rows

        Returns:
            Number of template agents successfully injected (0 on failure).
        """
        try:
            from polymarket_predictor.agents.templates import get_templates, get_stance_summary

            sim_dir = self._SIM_DATA_DIR / simulation_id
            config_path = sim_dir / "simulation_config.json"

            if not config_path.exists():
                logger.warning("Config not found at %s — skipping template injection", config_path)
                return 0

            config = json.loads(config_path.read_text(encoding="utf-8"))
            existing_agents = config.get("agent_configs", [])
            max_existing_id = max((a.get("agent_id", 0) for a in existing_agents), default=-1)

            templates = get_templates(max_agents=max_templates)

            # --- 1. Append agent configs ---
            for i, tmpl in enumerate(templates):
                agent_config = {
                    "agent_id": max_existing_id + 1 + i,
                    "entity_uuid": f"template_{tmpl['name']}",
                    "entity_name": tmpl["name"],
                    "entity_type": tmpl["type"],
                    "activity_level": tmpl["activity_level"],
                    "posts_per_hour": 2 if tmpl["activity_level"] > 0.5 else 1,
                    "comments_per_hour": 4 if tmpl["activity_level"] > 0.5 else 2,
                    "active_hours": list(range(8, 23)),
                    "response_delay_min": 15,
                    "response_delay_max": 60,
                    "sentiment_bias": tmpl["sentiment_bias"],
                    "stance": tmpl["stance"],
                    "influence_weight": tmpl["influence_weight"],
                }
                existing_agents.append(agent_config)

            config["agent_configs"] = existing_agents
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

            # --- 2. Append Reddit profiles ---
            reddit_path = sim_dir / "reddit_profiles.json"
            if reddit_path.exists():
                try:
                    reddit_profiles = json.loads(reddit_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, ValueError):
                    reddit_profiles = []

                next_uid = max((p.get("user_id", 0) for p in reddit_profiles), default=-1) + 1

                # OASIS requires these fields for Reddit agents
                mbti_types = ["INTJ", "ENTP", "ISFJ", "ESTP", "INFP", "ENTJ", "ISTJ", "ENFP"]
                genders = ["male", "female", "non-binary"]
                countries = ["US", "UK", "Canada", "Germany", "Japan", "Australia", "India", "France"]

                for i, tmpl in enumerate(templates):
                    reddit_profiles.append({
                        "user_id": next_uid + i,
                        "username": tmpl["name"],
                        "name": tmpl["name"].replace("_", " ").title(),
                        "bio": tmpl["bio"],
                        "persona": tmpl["bio"],
                        "karma": 100,
                        "created_at": "2024-01-01T00:00:00",
                        "profession": tmpl["type"],
                        # Required by OASIS agent generator
                        "mbti": mbti_types[i % len(mbti_types)],
                        "gender": genders[i % len(genders)],
                        "age": 25 + (i * 3) % 40,  # Range 25-64
                        "country": countries[i % len(countries)],
                    })
                # Ensure ALL profiles have required OASIS fields (organic profiles may be missing them)
                for j, profile in enumerate(reddit_profiles):
                    if "mbti" not in profile:
                        profile["mbti"] = mbti_types[j % len(mbti_types)]
                    if "gender" not in profile:
                        profile["gender"] = genders[j % len(genders)]
                    if "age" not in profile:
                        profile["age"] = 25 + (j * 3) % 40
                    if "country" not in profile:
                        profile["country"] = countries[j % len(countries)]

                reddit_path.write_text(json.dumps(reddit_profiles, indent=2, ensure_ascii=False), encoding="utf-8")

            # --- 3. Append Twitter profiles ---
            twitter_path = sim_dir / "twitter_profiles.csv"
            if twitter_path.exists():
                try:
                    with open(twitter_path, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        existing_rows = list(reader)
                        fieldnames = reader.fieldnames or []
                except Exception:
                    existing_rows = []
                    fieldnames = []

                next_uid = max((int(r.get("user_id", 0)) for r in existing_rows), default=-1) + 1 if existing_rows else 0

                for i, tmpl in enumerate(templates):
                    row = {
                        "user_id": str(next_uid + i),
                        "username": tmpl["name"],
                        "name": tmpl["name"].replace("_", " ").title(),
                        "bio": tmpl["bio"],
                        "persona": tmpl["bio"],
                        "friend_count": "50",
                        "follower_count": str(int(tmpl["influence_weight"] * 1000)),
                        "statuses_count": "100",
                        "created_at": "2024-01-01T00:00:00",
                    }
                    # Ensure all fieldnames present
                    for fn in fieldnames:
                        if fn not in row:
                            row[fn] = ""
                    for k in row:
                        if k not in fieldnames:
                            fieldnames.append(k)
                    existing_rows.append(row)

                if fieldnames and existing_rows:
                    with open(twitter_path, "w", encoding="utf-8", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(existing_rows)

            stance = get_stance_summary(templates)
            logger.info(
                "Injected %d template agents (bull=%d, bear=%d, neutral=%d). Total agents: %d",
                len(templates), stance["bullish"], stance["bearish"], stance["neutral"],
                len(existing_agents),
            )
            return len(templates)

        except Exception as e:
            logger.warning("Template agent injection failed: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _wait_for_task(self, endpoint: str, timeout: int = 300) -> dict:
        """Poll a GET task endpoint until completion or timeout."""
        elapsed = 0
        interval = 2
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            resp = await self.client.get(endpoint)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            status = data.get("status", "")
            progress = data.get("progress", 0)
            logger.info("Task progress: %s%% - %s", progress, data.get("message", ""))

            if status == "completed":
                return data
            if status == "failed":
                raise PipelineError(f"Task failed: {data.get('error', 'unknown')}")

        raise PipelineError(f"Task timed out after {timeout}s")

    async def _poll_post_status(
        self,
        endpoint: str,
        body: dict,
        timeout: int = 300,
    ) -> dict:
        """Poll a POST status endpoint with JSON body until completion or timeout."""
        elapsed = 0
        interval = 3
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            resp = await self.client.post(endpoint, json=body)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            status = data.get("status", "")
            progress = data.get("progress", 0)
            logger.info("Task progress: %s%% - %s", progress, data.get("message", ""))

            if status in ("completed", "ready"):
                return data
            if status == "failed":
                raise PipelineError(f"Task failed: {data.get('error', 'unknown')}")

        raise PipelineError(f"Task timed out after {timeout}s")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
