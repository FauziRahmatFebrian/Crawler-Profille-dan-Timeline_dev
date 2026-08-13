import random
from function.user_agents import USER_AGENTS

class UserAgentManager:
    def __init__(self, min_use=2):
        self.min_use = min_use
        self.usage_count = {ua: 0 for ua in USER_AGENTS}
        self._available = USER_AGENTS.copy()

    def get_user_agent(self):
        # kalau semua sudah dipakai >= min_use → reset
        if all(count >= self.min_use for count in self.usage_count.values()):
            self.usage_count = {ua: 0 for ua in USER_AGENTS}
            self._available = USER_AGENTS.copy()

        # kalau available kosong → reset juga
        if not self._available:
            self._available = [ua for ua in USER_AGENTS if self.usage_count[ua] < self.min_use]

        # pilih random dari yang masih tersedia
        ua = random.choice(self._available)
        self.usage_count[ua] += 1

        # kalau UA sudah mencapai min_use, hapus dari available
        if self.usage_count[ua] >= self.min_use:
            self._available.remove(ua)

        return ua
