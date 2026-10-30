"""Conservative, debounced client-exit detection without another process."""
class ClientLifetime:
    def __init__(self,grace=8):
        self.grace=grace;self.reset()
    def reset(self):
        self.seen=False;self.missing_since=None;self.children=set();self.fired=False
    def observe(self,parents,now,enabled=True):
        if not enabled:self.reset();return False
        if parents is None:
            # Access errors and partial snapshots are not evidence of an exit.
            self.missing_since=None;return False
        current=set(parents)
        self.children.intersection_update(current)
        self.children.update(pid for pid,parent in parents.items() if parent in current)
        roots=current-self.children
        if roots:
            self.seen=True;self.missing_since=None;self.fired=False;return False
        if not self.seen or self.fired:return False
        if self.missing_since is None:self.missing_since=now
        if now-self.missing_since<self.grace:return False
        self.fired=True;return True
