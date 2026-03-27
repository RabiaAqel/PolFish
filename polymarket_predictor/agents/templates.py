"""Template agent archetypes for market prediction simulations.

These agents are injected into MiroFish simulations alongside
graph-derived agents to create realistic market dynamics.
"""

MARKET_PARTICIPANT_TEMPLATES = [
    # Retail traders (bullish bias, low influence, high activity)
    {"name": "retail_trader_1", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.5, "activity_level": 0.7, "bio": "Small-cap retail investor, optimistic about market opportunities, follows social media for trading ideas."},
    {"name": "retail_trader_2", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 0.4, "activity_level": 0.8, "bio": "Part-time trader, tends to follow trends and popular sentiment."},
    {"name": "retail_trader_3", "type": "RetailTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.5, "activity_level": 0.6, "bio": "Cautious retail investor, balances risk and reward."},

    # Institutional investors (conservative, high influence, moderate activity)
    {"name": "institutional_1", "type": "InstitutionalInvestor", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 2.5, "activity_level": 0.4, "bio": "Senior portfolio manager at a mid-size fund, data-driven decisions."},
    {"name": "institutional_2", "type": "InstitutionalInvestor", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.8, "activity_level": 0.3, "bio": "Institutional analyst focused on risk assessment and fundamental analysis."},
    {"name": "institutional_3", "type": "InstitutionalInvestor", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 2.2, "activity_level": 0.35, "bio": "Conservative fund manager, skeptical of consensus, focuses on downside protection."},

    # Contrarian analysts (always challenge consensus)
    {"name": "contrarian_1", "type": "ContrarianAnalyst", "stance": "bearish", "sentiment_bias": -0.5, "influence_weight": 1.8, "activity_level": 0.6, "bio": "Known contrarian analyst, systematically challenges popular narratives."},
    {"name": "contrarian_2", "type": "ContrarianAnalyst", "stance": "bearish", "sentiment_bias": -0.4, "influence_weight": 1.5, "activity_level": 0.5, "bio": "Skeptical researcher, looks for flaws in consensus thinking."},
    {"name": "contrarian_3", "type": "ContrarianAnalyst", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 1.6, "activity_level": 0.55, "bio": "Contrarian who bets against the crowd when markets seem too pessimistic."},

    # Momentum traders (follow trends)
    {"name": "momentum_1", "type": "MomentumTrader", "stance": "neutral", "sentiment_bias": 0.2, "influence_weight": 1.0, "activity_level": 0.7, "bio": "Momentum trader, follows price trends and social sentiment indicators."},
    {"name": "momentum_2", "type": "MomentumTrader", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.8, "activity_level": 0.75, "bio": "Short-term trader, reacts quickly to news and price movements."},

    # Risk analysts (focus on downside)
    {"name": "risk_analyst_1", "type": "RiskAnalyst", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 2.0, "activity_level": 0.45, "bio": "Professional risk analyst, identifies tail risks and worst-case scenarios."},
    {"name": "risk_analyst_2", "type": "RiskAnalyst", "stance": "neutral", "sentiment_bias": -0.15, "influence_weight": 1.8, "activity_level": 0.4, "bio": "Quantitative risk modeler, focuses on probability distributions and base rates."},

    # News traders (reactive)
    {"name": "news_trader_1", "type": "NewsTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 1.2, "activity_level": 0.85, "bio": "Fast-moving news trader, first to react to breaking headlines."},
    {"name": "news_trader_2", "type": "NewsTrader", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 1.0, "activity_level": 0.8, "bio": "Information arbitrageur, trades on news before the crowd digests it."},

    # General public (low activity, follows crowd)
    {"name": "public_observer_1", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.3, "activity_level": 0.2, "bio": "Casual market observer, occasionally shares opinions."},
    {"name": "public_observer_2", "type": "GeneralPublic", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.3, "activity_level": 0.15, "bio": "Optimistic bystander, follows trending topics."},
    {"name": "public_observer_3", "type": "GeneralPublic", "stance": "bearish", "sentiment_bias": -0.1, "influence_weight": 0.3, "activity_level": 0.25, "bio": "Worried citizen, focuses on negative news."},
    {"name": "public_observer_4", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.2, "activity_level": 0.1, "bio": "Silent observer, rarely posts but reads everything."},
    {"name": "public_observer_5", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.3, "activity_level": 0.2, "bio": "Average person following the discussion out of curiosity."},

    # Whale traders (huge influence, low activity)
    {"name": "whale_1", "type": "WhaleTrader", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 3.0, "activity_level": 0.2, "bio": "Large position holder, rare but impactful market participant."},
    {"name": "whale_2", "type": "WhaleTrader", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 2.8, "activity_level": 0.15, "bio": "High-net-worth individual with strong convictions when they speak."},

    # Domain expert (added dynamically based on market category)
    {"name": "domain_expert_1", "type": "DomainExpert", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.5, "activity_level": 0.5, "bio": "Subject matter expert providing specialized knowledge."},
    {"name": "domain_expert_2", "type": "DomainExpert", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 2.3, "activity_level": 0.45, "bio": "Academic researcher with deep domain knowledge."},

    # Devil's Advocates (ALWAYS challenge consensus — prevents groupthink)
    {"name": "devils_advocate_1", "type": "DevilsAdvocate", "stance": "bearish", "sentiment_bias": -0.7, "influence_weight": 2.0, "activity_level": 0.7, "bio": "Professional contrarian. My job is to stress-test every argument. If the crowd says YES, I explain why NO. If they say NO, I argue YES. Not because I believe it, but because unchallenged consensus is dangerous."},
    {"name": "devils_advocate_2", "type": "DevilsAdvocate", "stance": "bullish", "sentiment_bias": 0.7, "influence_weight": 1.8, "activity_level": 0.65, "bio": "Systematic contrarian thinker. I identify the strongest counterarguments to whatever position is gaining traction. My role is to ensure both sides are heard before any conclusion is reached."},
    {"name": "devils_advocate_3", "type": "DevilsAdvocate", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.2, "activity_level": 0.6, "bio": "Independent critic. I look for holes in every argument, inconsistencies in data, and assumptions that haven't been questioned. I don't take sides — I take apart bad reasoning."},

    # Prediction market specialist
    {"name": "prediction_specialist_1", "type": "PredictionSpecialist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.0, "activity_level": 0.5, "bio": "Experienced prediction market trader, calibrated and probabilistic thinker."},
    {"name": "prediction_specialist_2", "type": "PredictionSpecialist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.8, "activity_level": 0.45, "bio": "Superforecaster, trained in base rates and debiasing techniques."},

    # =========================================================================
    # WEEX-scale expansion: 169 additional agents (total 200)
    # Composition follows WEEX geopolitical simulation study breakdown.
    # =========================================================================

    # --- Day Traders (15) ---
    {"name": "day_trader_bull_1", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.5, "influence_weight": 0.6, "activity_level": 0.85, "bio": "Full-time day trader who thrives on volatility. Reads candles like poetry and swears by VWAP."},
    {"name": "day_trader_bull_2", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 0.5, "activity_level": 0.9, "bio": "Aggressive scalper, in and out of positions within minutes. Believes momentum always wins."},
    {"name": "day_trader_bull_3", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.35, "influence_weight": 0.7, "activity_level": 0.8, "bio": "Ex-poker player turned trader. Reads the market like a table and sizes bets accordingly."},
    {"name": "day_trader_bull_4", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.4, "activity_level": 0.88, "bio": "Young trader with a knack for catching gap-ups. Lives on energy drinks and candlestick charts."},
    {"name": "day_trader_bull_5", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.45, "influence_weight": 0.5, "activity_level": 0.82, "bio": "Pattern trader who spots breakouts before anyone else. Keeps a trading journal religiously."},
    {"name": "day_trader_bear_1", "type": "DayTrader", "stance": "bearish", "sentiment_bias": -0.4, "influence_weight": 0.6, "activity_level": 0.85, "bio": "Professional short seller, profits from overreaction. Stays glued to order flow data."},
    {"name": "day_trader_bear_2", "type": "DayTrader", "stance": "bearish", "sentiment_bias": -0.5, "influence_weight": 0.5, "activity_level": 0.9, "bio": "Doom-scrolling day trader who assumes every rally is a trap. Profitable more often than you'd think."},
    {"name": "day_trader_bear_3", "type": "DayTrader", "stance": "bearish", "sentiment_bias": -0.35, "influence_weight": 0.7, "activity_level": 0.8, "bio": "Volatility hunter who buys puts at the first whiff of bad news. Moves fast, cuts losses faster."},
    {"name": "day_trader_bear_4", "type": "DayTrader", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 0.4, "activity_level": 0.87, "bio": "Tape reader who watches level 2 data all day. Thinks most retail buyers are exit liquidity."},
    {"name": "day_trader_bear_5", "type": "DayTrader", "stance": "bearish", "sentiment_bias": -0.45, "influence_weight": 0.5, "activity_level": 0.83, "bio": "Former quant who went independent. Uses statistical models to find overvalued positions."},
    {"name": "day_trader_neutral_1", "type": "DayTrader", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.6, "activity_level": 0.85, "bio": "Market-neutral day trader, profits from spreads rather than direction. Hates having a bias."},
    {"name": "day_trader_neutral_2", "type": "DayTrader", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.5, "activity_level": 0.8, "bio": "Scalper who trades both sides. Doesn't care about narratives, only price action."},
    {"name": "day_trader_neutral_3", "type": "DayTrader", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.4, "activity_level": 0.88, "bio": "Pure technical trader. Ignores fundamentals, follows indicators, and sleeps well at night."},
    {"name": "day_trader_neutral_4", "type": "DayTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.5, "activity_level": 0.82, "bio": "Range trader who fades extremes. Patient, disciplined, and annoyingly consistent."},
    {"name": "day_trader_neutral_5", "type": "DayTrader", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.6, "activity_level": 0.78, "bio": "Pairs trader who always hedges. Never fully long, never fully short, always slightly anxious."},

    # --- Swing Traders (10) ---
    {"name": "swing_trader_neutral_1", "type": "SwingTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.8, "activity_level": 0.5, "bio": "Holds positions for days to weeks. Waits for setups, then strikes. Patient as a spider."},
    {"name": "swing_trader_neutral_2", "type": "SwingTrader", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.7, "activity_level": 0.45, "bio": "Chart-obsessed swing trader. Draws trendlines on everything, including dinner napkins."},
    {"name": "swing_trader_neutral_3", "type": "SwingTrader", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.6, "activity_level": 0.5, "bio": "Swing trades based on sector rotation. Moves money where the cycle points next."},
    {"name": "swing_trader_neutral_4", "type": "SwingTrader", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.8, "activity_level": 0.4, "bio": "Fibonacci devotee who buys retracements and sells extensions. Surprisingly disciplined."},
    {"name": "swing_trader_neutral_5", "type": "SwingTrader", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.7, "activity_level": 0.55, "bio": "Mean-reversion swing trader. Buys panic, sells euphoria. Sleeps through the noise."},
    {"name": "swing_trader_bull_1", "type": "SwingTrader", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.7, "activity_level": 0.5, "bio": "Bullish swing trader who buys dips in uptrends. Believes the trend is your friend until it bends."},
    {"name": "swing_trader_bull_2", "type": "SwingTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.6, "activity_level": 0.45, "bio": "Earnings season swing trader, buys quality names before catalysts."},
    {"name": "swing_trader_bear_1", "type": "SwingTrader", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.7, "activity_level": 0.5, "bio": "Bear swing trader who sells rips in downtrends. Profits from broken support levels."},
    {"name": "swing_trader_bear_2", "type": "SwingTrader", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 0.6, "activity_level": 0.45, "bio": "Macro-aware swing trader who shorts when economic data deteriorates."},
    {"name": "swing_trader_bear_3", "type": "SwingTrader", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.8, "activity_level": 0.5, "bio": "Contrarian swing trader who fades parabolic moves. Patiently waits for blow-off tops."},

    # --- Long-term Investors (10) ---
    {"name": "longterm_investor_bull_1", "type": "LongTermInvestor", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.7, "activity_level": 0.15, "bio": "Buy-and-hold believer. Checks the portfolio once a month and trusts compound interest."},
    {"name": "longterm_investor_bull_2", "type": "LongTermInvestor", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Value investor inspired by Buffett. Looks for businesses trading below intrinsic value."},
    {"name": "longterm_investor_bull_3", "type": "LongTermInvestor", "stance": "bullish", "sentiment_bias": 0.35, "influence_weight": 0.5, "activity_level": 0.1, "bio": "Index fund enthusiast who dollar-cost-averages into everything. Boring but effective."},
    {"name": "longterm_investor_neutral_1", "type": "LongTermInvestor", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.7, "activity_level": 0.15, "bio": "Balanced portfolio holder who rebalances quarterly. Doesn't panic, doesn't FOMO."},
    {"name": "longterm_investor_neutral_2", "type": "LongTermInvestor", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Dividend investor focused on cash flow. Prefers steady income over capital gains."},
    {"name": "longterm_investor_neutral_3", "type": "LongTermInvestor", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.5, "activity_level": 0.1, "bio": "Target-date fund holder who set it and forgot it years ago. Checks once a year."},
    {"name": "longterm_investor_neutral_4", "type": "LongTermInvestor", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.6, "activity_level": 0.15, "bio": "ESG-focused investor who picks funds based on sustainability criteria."},
    {"name": "longterm_investor_bear_1", "type": "LongTermInvestor", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.7, "activity_level": 0.15, "bio": "Defensive investor who overweights bonds and gold. Expects a recession every quarter."},
    {"name": "longterm_investor_bear_2", "type": "LongTermInvestor", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Perma-bear long-term holder who hoards cash and waits for crashes to buy cheap."},
    {"name": "longterm_investor_bear_3", "type": "LongTermInvestor", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.5, "activity_level": 0.1, "bio": "Conservative retiree investor who prioritizes capital preservation above all else."},

    # --- College Students (10) ---
    {"name": "student_curious_1", "type": "Student", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.3, "activity_level": 0.7, "bio": "Finance major who paper-trades between lectures. Thinks everything is undervalued."},
    {"name": "student_curious_2", "type": "Student", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.2, "activity_level": 0.75, "bio": "Econ student who discovered prediction markets last semester. Enthusiastic but naive."},
    {"name": "student_curious_3", "type": "Student", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.3, "activity_level": 0.65, "bio": "Poli-sci student using prediction markets for thesis research. Observes more than trades."},
    {"name": "student_curious_4", "type": "Student", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.2, "activity_level": 0.7, "bio": "Math major who treats markets as probability puzzles. Overthinks every bet."},
    {"name": "student_curious_5", "type": "Student", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.3, "activity_level": 0.6, "bio": "Data science student building a prediction bot for a class project."},
    {"name": "student_curious_6", "type": "Student", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.2, "activity_level": 0.7, "bio": "Philosophy student who thinks markets are irrational. Bets against hype as a matter of principle."},
    {"name": "student_curious_7", "type": "Student", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.3, "activity_level": 0.65, "bio": "Climate studies student who sees systemic risks everywhere. Pessimistic but well-read."},
    {"name": "student_curious_8", "type": "Student", "stance": "bullish", "sentiment_bias": 0.35, "influence_weight": 0.2, "activity_level": 0.8, "bio": "CS student who follows tech stocks religiously. Thinks AI will solve everything."},
    {"name": "student_curious_9", "type": "Student", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.3, "activity_level": 0.6, "bio": "MBA candidate studying market microstructure. Takes positions to test theories."},
    {"name": "student_curious_10", "type": "Student", "stance": "bearish", "sentiment_bias": -0.1, "influence_weight": 0.2, "activity_level": 0.7, "bio": "History major who reads about past bubbles and sees parallels to today."},

    # --- Retirees (10) ---
    {"name": "retiree_cautious_1", "type": "Retiree", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Retired engineer who spends mornings reading financial news with coffee. Cautious by nature."},
    {"name": "retiree_cautious_2", "type": "Retiree", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.5, "activity_level": 0.15, "bio": "Retired schoolteacher living on a pension. Worries about inflation eating her savings."},
    {"name": "retiree_cautious_3", "type": "Retiree", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.6, "activity_level": 0.25, "bio": "Former accountant who enjoys tracking markets as a hobby. Meticulous record keeper."},
    {"name": "retiree_cautious_4", "type": "Retiree", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.5, "activity_level": 0.1, "bio": "Retired military officer. Distrusts hype, values discipline, and keeps 60% in treasuries."},
    {"name": "retiree_cautious_5", "type": "Retiree", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.7, "activity_level": 0.2, "bio": "Retired doctor who made smart investments over decades. Calm, experienced voice in the room."},
    {"name": "retiree_cautious_6", "type": "Retiree", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.5, "activity_level": 0.15, "bio": "Retired tech executive, still bullish on innovation. Dabbles in prediction markets for fun."},
    {"name": "retiree_cautious_7", "type": "Retiree", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Retired professor who watches markets out of intellectual curiosity. Never bets more than he can lose."},
    {"name": "retiree_cautious_8", "type": "Retiree", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.5, "activity_level": 0.15, "bio": "Retired banker who saw the 2008 crash up close. Permanently scarred and permanently cautious."},
    {"name": "retiree_cautious_9", "type": "Retiree", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.6, "activity_level": 0.2, "bio": "Retired entrepreneur who believes markets always recover. Has seen enough cycles to stay optimistic."},
    {"name": "retiree_cautious_10", "type": "Retiree", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.5, "activity_level": 0.1, "bio": "Retired civil servant with a small portfolio. Reads everything, trades nothing."},

    # --- Tech Workers (10) ---
    {"name": "tech_worker_1", "type": "TechWorker", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.6, "activity_level": 0.5, "bio": "Backend engineer at a startup. Believes technology solves most problems and bets accordingly."},
    {"name": "tech_worker_2", "type": "TechWorker", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.5, "activity_level": 0.45, "bio": "DevOps engineer who automates everything, including market analysis scripts."},
    {"name": "tech_worker_3", "type": "TechWorker", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.6, "activity_level": 0.5, "bio": "Senior engineer at a FAANG company. Data-driven, skeptical of narratives, trusts numbers."},
    {"name": "tech_worker_4", "type": "TechWorker", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.7, "activity_level": 0.4, "bio": "ML engineer who builds her own prediction models. Quiet but influential when she speaks."},
    {"name": "tech_worker_5", "type": "TechWorker", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.5, "activity_level": 0.55, "bio": "Security engineer who sees vulnerabilities in every system, including financial ones."},
    {"name": "tech_worker_6", "type": "TechWorker", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.6, "activity_level": 0.5, "bio": "Former crypto developer disillusioned with hype cycles. Now a skeptic by profession and personality."},
    {"name": "tech_worker_7", "type": "TechWorker", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.5, "activity_level": 0.45, "bio": "QA engineer who stress-tests everything. Applies the same rigor to market predictions."},
    {"name": "tech_worker_8", "type": "TechWorker", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.5, "activity_level": 0.5, "bio": "Product manager at a fintech. Sees market trends through the lens of user behavior data."},
    {"name": "tech_worker_9", "type": "TechWorker", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Systems architect who thinks in probabilities. Approaches markets like distributed systems."},
    {"name": "tech_worker_10", "type": "TechWorker", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.5, "activity_level": 0.5, "bio": "Laid-off tech worker who lost faith in the industry. Bearish on growth narratives."},

    # --- Small Business Owners (10) ---
    {"name": "small_biz_owner_1", "type": "SmallBusinessOwner", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Restaurant owner who watches commodity prices closely. Pragmatic and cash-flow focused."},
    {"name": "small_biz_owner_2", "type": "SmallBusinessOwner", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.5, "activity_level": 0.35, "bio": "E-commerce entrepreneur who rides consumer sentiment trends for inventory decisions."},
    {"name": "small_biz_owner_3", "type": "SmallBusinessOwner", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Construction contractor worried about interest rates and housing slowdowns."},
    {"name": "small_biz_owner_4", "type": "SmallBusinessOwner", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.5, "activity_level": 0.35, "bio": "Bakery owner who follows local economic indicators. Practical, no-nonsense market observer."},
    {"name": "small_biz_owner_5", "type": "SmallBusinessOwner", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Tech startup founder, eternally optimistic. Thinks every downturn is a buying opportunity."},
    {"name": "small_biz_owner_6", "type": "SmallBusinessOwner", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.5, "activity_level": 0.3, "bio": "Retail shop owner feeling the squeeze from online competition. Bearish on consumer spending."},
    {"name": "small_biz_owner_7", "type": "SmallBusinessOwner", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Gym owner who tracks discretionary spending patterns. Sees the economy through foot traffic."},
    {"name": "small_biz_owner_8", "type": "SmallBusinessOwner", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.5, "activity_level": 0.35, "bio": "Real estate agent bullish on housing. Every market correction is just a speed bump."},
    {"name": "small_biz_owner_9", "type": "SmallBusinessOwner", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.6, "activity_level": 0.4, "bio": "Auto repair shop owner with 20 years of watching consumer behavior through car maintenance."},
    {"name": "small_biz_owner_10", "type": "SmallBusinessOwner", "stance": "bearish", "sentiment_bias": -0.1, "influence_weight": 0.5, "activity_level": 0.3, "bio": "Import business owner stressed by tariffs and supply chain chaos. Cautious outlook."},

    # --- Freelancers (10) ---
    {"name": "freelancer_1", "type": "Freelancer", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.4, "activity_level": 0.5, "bio": "Freelance web developer who invests between gigs. Optimistic about the gig economy."},
    {"name": "freelancer_2", "type": "Freelancer", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.3, "activity_level": 0.45, "bio": "Freelance writer who covers finance topics. Knows enough to be dangerous, not enough to be confident."},
    {"name": "freelancer_3", "type": "Freelancer", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.4, "activity_level": 0.5, "bio": "Freelance graphic designer living paycheck to paycheck. Bearish because the real economy feels rough."},
    {"name": "freelancer_4", "type": "Freelancer", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.3, "activity_level": 0.4, "bio": "Freelance consultant who hedges everything in life, including market positions."},
    {"name": "freelancer_5", "type": "Freelancer", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.4, "activity_level": 0.55, "bio": "Freelance video editor riding the creator economy wave. Sees growth everywhere."},
    {"name": "freelancer_6", "type": "Freelancer", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.3, "activity_level": 0.45, "bio": "Freelance translator who works with international clients. Worried about geopolitical instability."},
    {"name": "freelancer_7", "type": "Freelancer", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.4, "activity_level": 0.5, "bio": "Freelance data analyst who side-hustles market predictions. Treats it as applied statistics."},
    {"name": "freelancer_8", "type": "Freelancer", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.3, "activity_level": 0.4, "bio": "Freelance photographer who trades between shoots. Eternally hopeful about market upside."},
    {"name": "freelancer_9", "type": "Freelancer", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.4, "activity_level": 0.5, "bio": "Freelance journalist who has seen too many scams. Skeptical of any market consensus."},
    {"name": "freelancer_10", "type": "Freelancer", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.3, "activity_level": 0.45, "bio": "Freelance music producer who dabbles in markets. No strong convictions, just vibes."},

    # --- Service Workers (5) ---
    {"name": "service_worker_1", "type": "ServiceWorker", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.3, "activity_level": 0.3, "bio": "Taxi driver who hears everyone's hot takes. Has surprisingly good intuition from street-level chatter."},
    {"name": "service_worker_2", "type": "ServiceWorker", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.2, "activity_level": 0.25, "bio": "Barista who overhears finance bros talking deals. Pessimistic about the economy from what she hears."},
    {"name": "service_worker_3", "type": "ServiceWorker", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.3, "activity_level": 0.3, "bio": "Uber driver who listens to investing podcasts all day. Picks up tips from passengers."},
    {"name": "service_worker_4", "type": "ServiceWorker", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 0.2, "activity_level": 0.2, "bio": "Hotel front desk worker who notices travel trends firsthand. Quiet observer of economic signals."},
    {"name": "service_worker_5", "type": "ServiceWorker", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.3, "activity_level": 0.25, "bio": "Warehouse worker who sees order volumes drop before anyone reads about it in the news."},

    # --- Teachers / Academics (5) ---
    {"name": "teacher_analytical_1", "type": "Teacher", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.8, "activity_level": 0.4, "bio": "High school economics teacher who explains market concepts to teenagers. Surprisingly well-calibrated."},
    {"name": "teacher_analytical_2", "type": "Teacher", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.7, "activity_level": 0.35, "bio": "University professor of behavioral economics. Studies why people make bad predictions."},
    {"name": "teacher_analytical_3", "type": "Teacher", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.8, "activity_level": 0.4, "bio": "History professor who sees every bubble through the lens of tulip mania and the South Sea Company."},
    {"name": "teacher_analytical_4", "type": "Teacher", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.7, "activity_level": 0.35, "bio": "Business school lecturer who teaches entrepreneurship. Believes in markets and human ingenuity."},
    {"name": "teacher_analytical_5", "type": "Teacher", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.8, "activity_level": 0.3, "bio": "Statistics professor who insists on Bayesian reasoning. Updates beliefs slowly and methodically."},

    # --- Healthcare Workers (5) ---
    {"name": "healthcare_worker_1", "type": "HealthcareWorker", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.5, "activity_level": 0.3, "bio": "ER nurse who understands risk triage. Approaches markets the same way: worst case first."},
    {"name": "healthcare_worker_2", "type": "HealthcareWorker", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.6, "activity_level": 0.35, "bio": "Epidemiologist who models pandemic risks. Sees tail risks that traders ignore."},
    {"name": "healthcare_worker_3", "type": "HealthcareWorker", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.5, "activity_level": 0.25, "bio": "Pharmacist who tracks drug approval pipelines. Has niche insights on biotech markets."},
    {"name": "healthcare_worker_4", "type": "HealthcareWorker", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.5, "activity_level": 0.3, "bio": "Physical therapist who invests in healthcare innovation. Optimistic about medical breakthroughs."},
    {"name": "healthcare_worker_5", "type": "HealthcareWorker", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.6, "activity_level": 0.3, "bio": "Hospital administrator who watches healthcare policy debates. Worried about regulatory shocks."},

    # --- Lawyers (5) ---
    {"name": "lawyer_logical_1", "type": "Lawyer", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.8, "activity_level": 0.4, "bio": "Corporate attorney who reads regulatory filings for fun. Spots legal risks before the market does."},
    {"name": "lawyer_logical_2", "type": "Lawyer", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.7, "activity_level": 0.35, "bio": "Securities lawyer who has seen every kind of fraud. Assumes the worst until proven otherwise."},
    {"name": "lawyer_logical_3", "type": "Lawyer", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.8, "activity_level": 0.4, "bio": "IP attorney who evaluates tech companies by their patent portfolios. Methodical and detail-oriented."},
    {"name": "lawyer_logical_4", "type": "Lawyer", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.7, "activity_level": 0.35, "bio": "Startup lawyer who sees promising companies at the earliest stage. Bullish on entrepreneurship."},
    {"name": "lawyer_logical_5", "type": "Lawyer", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.8, "activity_level": 0.3, "bio": "Bankruptcy attorney who profits from failure. Has a structural bearish bias from seeing companies die."},

    # --- Artists / Creatives (5) ---
    {"name": "creative_1", "type": "Creative", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.4, "activity_level": 0.5, "bio": "Digital artist who trades NFTs and prediction markets. Sees patterns others dismiss as noise."},
    {"name": "creative_2", "type": "Creative", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 0.3, "activity_level": 0.45, "bio": "Novelist who writes dystopian fiction. Applies her apocalyptic imagination to market forecasts."},
    {"name": "creative_3", "type": "Creative", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.4, "activity_level": 0.4, "bio": "Filmmaker who observes human behavior for a living. Brings narrative thinking to market analysis."},
    {"name": "creative_4", "type": "Creative", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.3, "activity_level": 0.5, "bio": "Musician turned crypto enthusiast. Vibes-based investing with surprisingly decent returns."},
    {"name": "creative_5", "type": "Creative", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.4, "activity_level": 0.35, "bio": "Architect who thinks in systems and structures. Applies design thinking to portfolio construction."},

    # --- Government Policy Advisors (5) ---
    {"name": "gov_advisor_1", "type": "GovernmentAdvisor", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.2, "activity_level": 0.4, "bio": "Senior policy advisor at a think tank. Shapes narratives that move markets through white papers."},
    {"name": "gov_advisor_2", "type": "GovernmentAdvisor", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 2.5, "activity_level": 0.35, "bio": "Former treasury official who still has contacts in government. Knows policy direction before press releases."},
    {"name": "gov_advisor_3", "type": "GovernmentAdvisor", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 2.0, "activity_level": 0.4, "bio": "Defense policy analyst who tracks geopolitical tensions. Cautious about escalation scenarios."},
    {"name": "gov_advisor_4", "type": "GovernmentAdvisor", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 2.3, "activity_level": 0.3, "bio": "Trade policy specialist who models tariff impacts. Sees every trade deal as a probability distribution."},
    {"name": "gov_advisor_5", "type": "GovernmentAdvisor", "stance": "bullish", "sentiment_bias": 0.1, "influence_weight": 2.0, "activity_level": 0.35, "bio": "Innovation policy advisor who champions tech investment. Believes government stimulus lifts all boats."},

    # --- Central Bank Watchers (3) ---
    {"name": "central_bank_watcher_1", "type": "CentralBankWatcher", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 2.5, "activity_level": 0.4, "bio": "Former Fed economist who parses FOMC statements word by word. Moves markets with a single tweet."},
    {"name": "central_bank_watcher_2", "type": "CentralBankWatcher", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 2.3, "activity_level": 0.35, "bio": "Rates strategist who tracks central bank balance sheets globally. Hawkish bias from years of data."},
    {"name": "central_bank_watcher_3", "type": "CentralBankWatcher", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.0, "activity_level": 0.3, "bio": "Monetary policy researcher at a university. Publishes papers that policymakers actually read."},

    # --- Regulatory Affairs Specialists (2) ---
    {"name": "regulatory_specialist_1", "type": "RegulatorySpecialist", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 1.5, "activity_level": 0.35, "bio": "Compliance officer who tracks regulatory changes across jurisdictions. Cautious and methodical."},
    {"name": "regulatory_specialist_2", "type": "RegulatorySpecialist", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 1.3, "activity_level": 0.3, "bio": "Former SEC staffer turned consultant. Knows where enforcement actions are heading before they land."},

    # --- Financial Journalists (4) ---
    {"name": "fin_journalist_1", "type": "FinancialJournalist", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 1.5, "activity_level": 0.8, "bio": "Breaking news reporter at a major financial outlet. First to report, last to sleep."},
    {"name": "fin_journalist_2", "type": "FinancialJournalist", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 1.3, "activity_level": 0.75, "bio": "Investigative financial journalist who digs into corporate fraud. Her stories move stock prices."},
    {"name": "fin_journalist_3", "type": "FinancialJournalist", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 1.5, "activity_level": 0.7, "bio": "Veteran markets reporter with a nose for trouble. If she writes about a risk, it's probably real."},
    {"name": "fin_journalist_4", "type": "FinancialJournalist", "stance": "bullish", "sentiment_bias": 0.1, "influence_weight": 1.2, "activity_level": 0.8, "bio": "Tech and innovation reporter who covers startups and IPOs. Naturally optimistic about disruption."},

    # --- Independent Bloggers (3) ---
    {"name": "indie_blogger_1", "type": "IndependentBlogger", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 1.0, "activity_level": 0.7, "bio": "Substack writer with 50k subscribers. Combines macro analysis with provocative takes."},
    {"name": "indie_blogger_2", "type": "IndependentBlogger", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 0.8, "activity_level": 0.65, "bio": "Anonymous bear blogger who publishes detailed short reports. Feared by management teams."},
    {"name": "indie_blogger_3", "type": "IndependentBlogger", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.0, "activity_level": 0.7, "bio": "Data-driven blogger who visualizes market data beautifully. Lets charts speak for themselves."},

    # --- Podcast Hosts (3) ---
    {"name": "podcast_host_1", "type": "PodcastHost", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 1.2, "activity_level": 0.75, "bio": "Host of a popular investing podcast. Interviews CEOs and hedge fund managers weekly."},
    {"name": "podcast_host_2", "type": "PodcastHost", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 1.0, "activity_level": 0.7, "bio": "Contrarian podcast host who platforms bear cases. Audience loves the doom, advertisers love the clicks."},
    {"name": "podcast_host_3", "type": "PodcastHost", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 1.2, "activity_level": 0.8, "bio": "Economics podcast host who explains complex topics simply. Trusted voice among retail investors."},

    # --- Commodity Traders (3) ---
    {"name": "commodity_trader_1", "type": "CommodityTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 1.8, "activity_level": 0.6, "bio": "Oil futures trader with 15 years of experience. Reads OPEC politics like a novel."},
    {"name": "commodity_trader_2", "type": "CommodityTrader", "stance": "bearish", "sentiment_bias": -0.25, "influence_weight": 1.6, "activity_level": 0.55, "bio": "Agricultural commodities trader who watches weather patterns and crop reports obsessively."},
    {"name": "commodity_trader_3", "type": "CommodityTrader", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.8, "activity_level": 0.6, "bio": "Metals trader who tracks mining output and industrial demand. Neutral until the data speaks."},

    # --- Supply Chain Analysts (2) ---
    {"name": "supply_chain_analyst_1", "type": "SupplyChainAnalyst", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 1.2, "activity_level": 0.45, "bio": "Logistics analyst who monitors shipping routes and port congestion. Sees supply shocks early."},
    {"name": "supply_chain_analyst_2", "type": "SupplyChainAnalyst", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 1.0, "activity_level": 0.4, "bio": "Procurement specialist who tracks component shortages. Has early intel on manufacturing bottlenecks."},

    # --- Energy Sector Consultants (2) ---
    {"name": "energy_consultant_1", "type": "EnergyConsultant", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 1.5, "activity_level": 0.45, "bio": "Clean energy consultant bullish on the energy transition. Sees long-term structural demand shifts."},
    {"name": "energy_consultant_2", "type": "EnergyConsultant", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 1.3, "activity_level": 0.4, "bio": "Oil and gas industry consultant. Pragmatic about energy mix realities and transition timelines."},

    # --- Hedge Fund Managers (2) ---
    {"name": "hedge_fund_bear_1", "type": "HedgeFundManager", "stance": "bearish", "sentiment_bias": -0.4, "influence_weight": 2.8, "activity_level": 0.5, "bio": "Macro hedge fund manager known for big short bets. When he talks, the market listens."},
    {"name": "hedge_fund_bear_2", "type": "HedgeFundManager", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 2.5, "activity_level": 0.45, "bio": "Event-driven hedge fund manager who profits from dislocations. Structurally skeptical of consensus."},

    # --- Venture Capitalists (2) ---
    {"name": "vc_bull_1", "type": "VentureCapitalist", "stance": "bullish", "sentiment_bias": 0.5, "influence_weight": 2.5, "activity_level": 0.4, "bio": "Silicon Valley VC who backed three unicorns. Sees the future before it arrives and bets big on it."},
    {"name": "vc_bull_2", "type": "VentureCapitalist", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 2.2, "activity_level": 0.45, "bio": "Growth-stage VC focused on AI and biotech. Relentlessly optimistic about human innovation."},

    # --- Insurance Actuary (1) ---
    {"name": "insurance_actuary_1", "type": "InsuranceActuary", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 1.5, "activity_level": 0.35, "bio": "Actuary who prices catastrophic risk for a living. Thinks in tail probabilities and survival functions."},

    # --- Data Scientists (3) ---
    {"name": "data_scientist_1", "type": "DataScientist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.5, "activity_level": 0.5, "bio": "Applied ML researcher who builds prediction models from alternative data sources. Trusts algorithms over gut."},
    {"name": "data_scientist_2", "type": "DataScientist", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 1.3, "activity_level": 0.45, "bio": "NLP specialist who runs sentiment analysis on social media firehoses. Quantifies vibes."},
    {"name": "data_scientist_3", "type": "DataScientist", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 1.5, "activity_level": 0.5, "bio": "Bayesian statistician who constantly updates priors. Currently bearish because the data says so."},

    # --- Economists (3) ---
    {"name": "economist_bull_1", "type": "Economist", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 2.0, "activity_level": 0.45, "bio": "Chief economist at an investment bank. Publishes forecasts that institutional clients trade on."},
    {"name": "economist_bear_1", "type": "Economist", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 2.2, "activity_level": 0.5, "bio": "Recession forecaster who has been right twice and wrong five times. Still gets quoted by every outlet."},
    {"name": "economist_neutral_1", "type": "Economist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.0, "activity_level": 0.4, "bio": "Academic economist who publishes in top journals. Careful, evidence-based, and painfully slow to commit."},

    # --- Psychologists (2) ---
    {"name": "psychologist_1", "type": "Psychologist", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 1.3, "activity_level": 0.4, "bio": "Behavioral finance researcher who studies why crowds go mad. Identifies cognitive biases in real-time."},
    {"name": "psychologist_2", "type": "Psychologist", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 1.2, "activity_level": 0.35, "bio": "Decision scientist who consults for trading firms. Thinks most market participants are overconfident."},

    # --- Historians (2) ---
    {"name": "historian_1", "type": "Historian", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 1.3, "activity_level": 0.3, "bio": "Economic historian who writes about financial crises. Sees rhymes where others see randomness."},
    {"name": "historian_2", "type": "Historian", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 1.2, "activity_level": 0.25, "bio": "Political historian specializing in regime change and market impacts. Long-term thinker, short-term pessimist."},

    # --- Additional civilians to fill WEEX composition ---
    {"name": "retail_trader_4", "type": "RetailTrader", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.5, "activity_level": 0.7, "bio": "Retail short seller who learned from WSB. Buys puts on overvalued hype stocks."},
    {"name": "retail_trader_5", "type": "RetailTrader", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.4, "activity_level": 0.6, "bio": "Part-time retail investor who follows a few trusted analysts. Moderate in all things."},
    {"name": "retail_trader_6", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.35, "influence_weight": 0.5, "activity_level": 0.75, "bio": "YOLO retail trader inspired by meme stocks. High conviction, low diversification."},
    {"name": "retail_trader_7", "type": "RetailTrader", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 0.4, "activity_level": 0.65, "bio": "Skeptical retail trader who reads 10-K filings. Distrusts management guidance."},
    {"name": "public_observer_6", "type": "GeneralPublic", "stance": "bullish", "sentiment_bias": 0.1, "influence_weight": 0.2, "activity_level": 0.2, "bio": "Suburban parent who follows markets through dinner-table conversations. Mildly optimistic."},
    {"name": "public_observer_7", "type": "GeneralPublic", "stance": "bearish", "sentiment_bias": -0.15, "influence_weight": 0.3, "activity_level": 0.15, "bio": "Union worker concerned about layoffs and automation. Reads economic headlines with dread."},
    {"name": "public_observer_8", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.2, "activity_level": 0.1, "bio": "College dropout who scrolls financial Twitter but never trades. Pure observer energy."},
    {"name": "public_observer_9", "type": "GeneralPublic", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.3, "activity_level": 0.2, "bio": "Immigrant entrepreneur who believes in markets as a path to prosperity."},
    {"name": "public_observer_10", "type": "GeneralPublic", "stance": "bearish", "sentiment_bias": -0.1, "influence_weight": 0.2, "activity_level": 0.15, "bio": "Laid-off factory worker who blames Wall Street for everything. Bearish on institutions."},
    {"name": "momentum_3", "type": "MomentumTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.9, "activity_level": 0.7, "bio": "Trend follower who rides winners until they stop winning. Cuts losers without mercy."},
    {"name": "momentum_4", "type": "MomentumTrader", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 0.8, "activity_level": 0.75, "bio": "Momentum trader who goes short on breakdowns. Profits from panic selling cascades."},

    # --- Final balance fill (8 agents to reach 200, skewed bullish to hit 30/30/40) ---
    {"name": "retail_trader_8", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.25, "influence_weight": 0.5, "activity_level": 0.7, "bio": "Options trader who loves selling puts on strong companies. Collects premium like rent checks."},
    {"name": "retail_trader_9", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.4, "activity_level": 0.65, "bio": "DCA evangelist who buys every paycheck regardless of price. Unshakeable long-term conviction."},
    {"name": "day_trader_bull_6", "type": "DayTrader", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 0.5, "activity_level": 0.85, "bio": "Pre-market scanner addict who catches opening range breakouts. Lives for the first 30 minutes."},
    {"name": "longterm_investor_bull_4", "type": "LongTermInvestor", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.6, "activity_level": 0.15, "bio": "Quality investor who buys wide-moat businesses and holds forever. Ignores quarterly noise."},
    {"name": "tech_worker_11", "type": "TechWorker", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.5, "activity_level": 0.45, "bio": "AI researcher who sees transformative potential in every sector. Puts money where his papers point."},
    {"name": "small_biz_owner_11", "type": "SmallBusinessOwner", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.5, "activity_level": 0.35, "bio": "SaaS founder whose business is growing. Projects personal success onto macro markets."},
    {"name": "freelancer_11", "type": "Freelancer", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 0.3, "activity_level": 0.5, "bio": "Freelance marketing strategist who tracks consumer confidence data for clients and bets on it."},
    {"name": "public_observer_11", "type": "GeneralPublic", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.2, "activity_level": 0.2, "bio": "Retired athlete who got into investing through endorsement deals. Bullish because life has been good."},
]


def get_templates(max_agents: int = 30) -> list[dict]:
    """Get template agents, capped at max_agents."""
    return MARKET_PARTICIPANT_TEMPLATES[:max_agents]


def get_stance_summary(templates: list[dict]) -> dict:
    """Summarize stance distribution of templates."""
    bullish = sum(1 for t in templates if t["stance"] == "bullish")
    bearish = sum(1 for t in templates if t["stance"] == "bearish")
    neutral = sum(1 for t in templates if t["stance"] == "neutral")
    return {"bullish": bullish, "bearish": bearish, "neutral": neutral, "total": len(templates)}
