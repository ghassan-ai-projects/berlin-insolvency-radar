"""Global test configuration for Berlin Insolvency Radar.

Sets BI_RADAR_USE_MOCK_AGENTS=1 for all non-live tests so that
the agent modules (extraction, risk review) use mock/placeholder results
instead of hitting the DeepSeek API. Live E2E tests override this
by clearing the variable.
"""

import os

# Default: use mock agents for all tests.
# Live tests (marked @pytest.mark.live) should clear this env var
# before importing agent modules so they hit the real API.
os.environ.setdefault("BI_RADAR_USE_MOCK_AGENTS", "1")
