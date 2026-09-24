Create tonight's Market Primer briefing for the Indian stock market.

Follow the instructions in automation/daily-briefing.md exactly, step by step:
check the date and whether a briefing is needed, research today's session with web
search, write briefings/<today>.json, add one missing Basics lesson if any, run
python3 scripts/validate.py until it prints OK, then commit and push to main.

If the market was closed today, or today's briefing already exists, stop without
committing. Never invent numbers. Finish with a short summary of what you published.
