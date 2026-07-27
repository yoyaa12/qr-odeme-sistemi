import asyncio
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str):
        def decorator(callback: Callable):
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            return callback
        return decorator

    async def publish(self, event_type: str, *args, **kwargs):
        if event_type in self._subscribers:
            # Execute all callbacks concurrently
            tasks = [callback(*args, **kwargs) for callback in self._subscribers[event_type]]
            if tasks:
                await asyncio.gather(*tasks)

event_bus = EventBus()
