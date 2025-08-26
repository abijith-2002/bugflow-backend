# Backend dependencies notes

This backend targets Python 3.12.

Changes made to fix installation:
- gotrue pinned from 2.10.1 (non-existent on PyPI) to 2.10.0 which is the nearest available version. This resolves pip install failure.

Compatibility overview:
- fastapi==0.115.12 requires starlette>=0.46 and pydantic v2; current pins (starlette==0.46.1, pydantic==2.11.3, pydantic_core==2.33.1, typing_extensions==4.13.1) are compatible.
- supabase==2.6.0 pulls in postgrest, realtime, storage3, gotrue; our explicit pins match compatible recent versions.

If future installation errors arise due to environment constraints:
- On Python <3.10 some packages will fail; please ensure Python 3.10+ (3.11/3.12 recommended).
- For optional dev extras like uvloop/httptools on unsupported platforms, you may remove them for constrained environments.

To install:
pip install -r requirements.txt
