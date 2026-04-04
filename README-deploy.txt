MacMarket deploy refresh

Files included:
- deploy-macmarket-trader.bat
- restart-macmarket-trader.bat
- scripts\deploy_windows.bat
- scripts\restart_windows.bat

Default target:
C:\Dashboard\MacMarket-Trader

How to use:
1) Copy these files into the repo, overwriting the old deploy/restart scripts.
2) Run deploy-macmarket-trader.bat from the repo root.
3) Optional environment variables before running:
   set RUN_TESTS=1
   set RUN_E2E=1
   set STRICT_NODE=1
4) Optional target override:
   deploy-macmarket-trader.bat "C:\Dashboard\MacMarket-Trader"

Notes:
- If you run the deploy from C:\Dashboard\MacMarket-Trader itself, it detects source == destination and skips robocopy.
- If you run it from a different clone, it mirrors into C:\Dashboard\MacMarket-Trader while preserving runtime artifacts.
- It warns on Node mismatch by default; set STRICT_NODE=1 to make that a hard fail.
