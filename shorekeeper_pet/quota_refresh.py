"""Manual refresh feedback, separate from cached quota updates and speech."""
import threading
import time


class QuotaRefresh:
    def __init__(self, event, clock=time.monotonic):
        self.event=event; self.clock=clock; self.lock=threading.Lock()
        self.sequence=0; self.pending=None; self.started=0; self.context=None
        self.loading_until=0; self.failure_until=0

    def request(self,context=None):
        with self.lock:
            # Repeated clicks coalesce while a request is outstanding.
            if self.pending is not None and context==self.context:return
            self.context=context
            self.sequence+=1; self.pending=self.sequence; self.started=self.clock()
            self.loading_until=0; self.failure_until=0
            self.event.set()

    def begin_read(self):
        # Capture the request and consume its wakeup atomically. A click during
        # an older in-flight read stays queued for the following iteration.
        with self.lock:
            self.event.clear()
            return self.sequence

    def finish(self, ticket, result):
        with self.lock:
            if self.pending is None or ticket!=self.pending:return
            self.pending=None
            self.loading_until=max(self.clock(),self.started+.6)
            self.failure_until=self.loading_until+2.5 if result.get('error') or result.get('source')!='live' else 0

    def label(self):
        with self.lock:
            if self.pending is not None or self.clock()<self.loading_until:return '刷新中…'
            if self.clock()<self.failure_until:return '刷新失败'
            return ''
