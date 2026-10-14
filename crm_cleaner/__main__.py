"""让 ``python -m crm_cleaner`` 能直接跑。"""
from .cli import main

raise SystemExit(main())
