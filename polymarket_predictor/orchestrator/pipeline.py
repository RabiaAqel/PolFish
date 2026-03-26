"""MiroFish pipeline orchestrator — drives the full API lifecycle programmatically."""

import asyncio
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
        self.client = httpx.AsyncClient(base_url=base_url, timeout=300.0)

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

        # Step 4: Run simulation
        await self.run_simulation(sim_id, max_rounds)
        logger.info("Simulation completed: %s", sim_id)

        # Step 5: Generate report
        report = await self.generate_report(sim_id)
        logger.info("Report generated: %s", report.get("report_id", "unknown"))

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
        await self._wait_for_task(f"/graph/task/{task_id}", timeout=300)

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
            timeout = 600
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
