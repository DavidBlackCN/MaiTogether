"""Only injected into isolated copies: seed states, suspend external background work.

The upstream read API, life engine, wake logic and hooks remain unmodified.
"""
import asyncio
from contextlib import suppress
from datetime import timedelta
from maibot_sdk import API


class AcceptanceProbe:
    async def on_load(self):
        await self._upstream_load()
        self.worker.cancel()
        with suppress(asyncio.CancelledError): await self.worker
        await self.acceptance_state()

    @API('acceptance_state', public=False, version='1')
    async def acceptance_state(self, kind='leisure', age=0, awake=False, all_day=False, gap=False, **kwargs):
        from .core.models import PlanInput
        now=self.now()
        self.config.life.schedule_enabled=not all_day
        with self.store.db:
            for row in self.store.all('plan'): self.store.delete('plan',row['id'])
            self.store.delete('runtime','awakening')
            state=self.engine.state()
            self.store.put('state',{**state,'updated_at':(now-timedelta(seconds=age)).isoformat()})
        if kind:
            self.engine.create_plan(PlanInput(title='isolated fixture',kind=kind,location='home',
                start=now.isoformat(),end=(now+timedelta(minutes=10)).isoformat()),'',now,autonomous=True)
        if awake or gap:
            with self.store.db:
                self.store.put('runtime',{'id':'awakening','until':(now+timedelta(seconds=60 if awake else -1)).isoformat(),
                    'sleep_end':(now+timedelta(minutes=10)).isoformat(),'sleep_location':'home','session_id':'','user_id':''})
        return {'status': await self.get_life_status(), 'internal_sleeping': self.living.sleeping(now)}

    @API('acceptance_person', public=False, version='1')
    async def acceptance_person(self, stream_id, user_id='10001'):
        await self.identify_person(stream_id,user_id,'qq')
        p=self.anniversaries.save_profile('fixture',stream_id,user_id=user_id)
        with self.store.db: self.store.put('profile',{**p,'intimacy':3,'intimacy_mode':'manual'})
        return True
