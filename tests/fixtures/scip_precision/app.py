"""Precision demo fixture.

Two classes define a ``handle()`` method. ``run()`` calls ``A.handle`` — but the
built-in backend's bare-name heuristic links the call to the *first* project
function named ``handle`` (``B.handle``, defined earlier), which is wrong. A SCIP
index resolves the call to ``A.handle``; the precision pass folds that in.
"""


class B:
    def handle(self):
        return "b"


class A:
    def handle(self):
        return "a"


def run():
    a = A()
    return a.handle()
