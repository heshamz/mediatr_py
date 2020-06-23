from typing import Callable,Any
import inspect
from mediatr.exceptions import raise_if_behavior_is_invalid, raise_if_handler_is_invalid, raise_if_handler_not_found, raise_if_request_invalid

__handlers__ = {}
__behaviors__ = {}

def extract_request_type(handler,is_behavior=False) ->type:
    isfunc = inspect.isfunction(handler)
    func = handler if isfunc else (handler.handle if hasattr(handler,'handle') else None)
    
    if is_behavior:
        raise_if_behavior_is_invalid(handler)
    else:
        raise_if_handler_is_invalid(handler)
    
    sign = inspect.signature(func)
    items = list(sign.parameters)
    return sign.parameters.get(items[0]).annotation if isfunc else sign.parameters.get(items[1]).annotation


async def __return_await__(result):
    return await result if inspect.isawaitable(result) or inspect.iscoroutine(result) else result


def find_behaviors(request):
    r_class = request.__class__
    behaviors = []
    for key,val in __behaviors__.items():
        if key== r_class or issubclass(r_class,key) or key == Any:
            behaviors = behaviors + val
    return behaviors


class Mediator():
    
    
    def __init__(self,handler_class_manager:Callable = None):
        if not handler_class_manager:
            self.handler_class_manager = lambda X,is_behavior=False: X()
    
    handler_class_manager = None

    
    async def send_async(self,request):

        raise_if_request_invalid(request)

        handler  = __handlers__[request.__class__] if __handlers__.get(request.__class__) else None
        raise_if_handler_not_found(handler,__handlers__)
        
        handler_func = None
        handler_obj=None

        if inspect.isfunction(handler):
            handler_func = handler
        else:
            handler_obj = self.handler_class_manager(handler)
            handler_func = handler_obj.handle

        behaviors = find_behaviors(request)
        gen = None

        def start_func():
            for behavior in behaviors:
                if inspect.isfunction(behavior):
                    beh_func = behavior
                else:
                    beh_obj = self.handler_class_manager(behavior,True)
                    beh_func = beh_obj.handle
                yield beh_func(request,next_func)
            yield handler_func(request)

        gen = start_func()

        async def next_func():
            return await __return_await__(next(gen))

        result = await next_func()
        return await __return_await__(result)
       

    @staticmethod
    def register_handler(handler):
        request_type = extract_request_type(handler)
        if not __handlers__.get(request_type):
            __handlers__[request_type] = handler


    @staticmethod
    def register_behavior(behavior):
        request_type = extract_request_type(behavior,True)
        if not __behaviors__.get(request_type):
            __behaviors__[request_type] = []
        if not any( x==behavior for x in __behaviors__[request_type]):
            __behaviors__[request_type].append(behavior)

    
    @staticmethod
    def handler(handler):
        Mediator.register_handler(handler)
        return handler

    @staticmethod
    def behavior(behavior):
        Mediator.register_behavior(behavior)
        return behavior