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
    async def acceptance_state(self, kind='leisure', age=0, awake=False, all_day=False, nap_quiet=True, **kwargs):
        from .core.models import PlanInput
        now=self.now()
        self.config.life.schedule_enabled=not all_day
        self.config.life.nap_quiet=nap_quiet
        with self.store.db:
            for row in self.store.all('plan'): self.store.delete('plan',row['id'])
            self.store.delete('runtime','awakening')
            state=self.engine.state()
            self.store.put('state',{**state,'updated_at':(now-timedelta(seconds=age)).isoformat()})
        if kind:
            self.engine.create_plan(PlanInput(title='isolated fixture',kind=kind,location='home',
                start=now.isoformat(),end=(now+timedelta(minutes=10)).isoformat()),'',now,autonomous=True)
        if awake:
            with self.store.db:
                self.store.put('runtime',{'id':'awakening','until':(now+timedelta(seconds=60)).isoformat(),
                    'sleep_end':(now+timedelta(minutes=10)).isoformat(),'sleep_location':'home','session_id':'','user_id':''})
        return {'status': await self.get_life_status(), 'internal_sleeping': self.living.sleeping(now)}

    @API('acceptance_expire_wake', public=False, version='1')
    async def acceptance_expire_wake(self):
        now = self.now()
        wake = self.store.get('runtime', 'awakening')
        with self.store.db:
            self.store.put('runtime', {**wake, 'until': (now-timedelta(seconds=1)).isoformat()})
        before = list(self.store.db.iterdump())
        status = await self.get_life_status()
        behavior = await self.evaluate_behavior('proactive')
        return {'status': status, 'behavior': behavior, 'internal_sleeping': self.living.sleeping(now),
                'read_only': before == list(self.store.db.iterdump())}

    @API('acceptance_person', public=False, version='1')
    async def acceptance_person(self, stream_id, user_id='10001'):
        await self.identify_person(stream_id,user_id,'qq')
        p=self.anniversaries.save_profile('fixture',stream_id,user_id=user_id)
        with self.store.db: self.store.put('profile',{**p,'intimacy':3,'intimacy_mode':'manual'})
        return True

    @API('acceptance_delivery', public=False, version='1')
    async def acceptance_delivery(self, mode='space', stream_id='', suffix='one'):
        from .integrations.together import deliver, DeliveryProblem
        from .integrations.qzone import DiaryPublisher
        try:
            if mode == 'message':
                return await deliver(self.ctx, 'message', {'stream_id': stream_id,
                    'segments': [{'type': 'text', 'content': 'isolated life sharing'}],
                    'storage_message': True, 'sync_to_maisaka_history': True})
            day = 'fixture-' + suffix
            self.config.diary.publish_mode = '手动发布'
            pub = self.diary_publisher
            if not self.store.find('diary_publication', day):
                pub.put({'id': day, 'day': day, 'status': '草稿', 'content': 'isolated public diary'})
            await pub.publish(day, self.now())
            return self.store.get('diary_publication', day)
        except DeliveryProblem as error:
            return {'state': error.state, 'status': self.store.get('diary_publication', day)['status'] if mode == 'space' else '', 'error': str(error)}

    @API('acceptance_share', public=False, version='1')
    async def acceptance_share(self, stream_id):
        from .core.models import ExperienceInput
        from .integrations.together import DeliveryProblem
        now = self.now()
        cfg = self.config.proactive
        cfg.enabled, cfg.mode, cfg.session_ids = True, '主动表达', [stream_id]
        cfg.start_hour = cfg.end_hour = 0
        cfg.daily_limit, cfg.cooldown_minutes = 10, 1
        self.engine.record_experience(ExperienceInput(summary='isolated reading', importance=8,
            occurred_at=now.isoformat(), source='simulated', evidence='fixture'), stream_id, now)
        try:
            await self.living.share(now)
        except DeliveryProblem:
            pass
        finally:
            cfg.enabled = False
        return self.store.all('share_receipt')
