import inspect
from typing import Any, Awaitable, Callable, Optional, TypeVar, Generic, Union
from enum import Enum

from mediatr.exceptions import (
    raise_if_behavior_is_invalid,
    raise_if_handler_is_invalid,
    raise_if_handler_not_found,
    raise_if_notifiacation_is_invalid,
    raise_if_request_none,
)


class RequestType(Enum):
    HANDLER = 0
    NOTIFICATION = 1
    BEHAVIOR = 2


__handlers__ = {}
__notifications__ = {}
__behaviors__ = {}

TResponse = TypeVar("TResponse")


class GenericQuery(Generic[TResponse]):
    pass


@staticmethod
def default_handler_class_manager(HandlerCls: type):
    return HandlerCls()


def extract_request_type(handler, request_type: RequestType) -> type:
    isfunc = inspect.isfunction(handler)

    func = None
    if isfunc:
        func = handler
    else:
        if hasattr(handler, "handle"):
            if inspect.isfunction(handler.handle):
                func = handler.handle
            elif inspect.ismethod(handler.handle):
                func = handler.__class__.handle

    if request_type == RequestType.HANDLER:
        raise_if_handler_is_invalid(handler)
    elif request_type == RequestType.NOTIFICATION:
        raise_if_notifiacation_is_invalid(handler)
    elif request_type == RequestType.BEHAVIOR:
        raise_if_behavior_is_invalid(handler)

    sign = inspect.signature(func)
    items = list(sign.parameters)
    return (
        sign.parameters.get(items[0]).annotation
        if isfunc
        else sign.parameters.get(items[1]).annotation
    )


async def __return_await__(result):
    return (
        await result
        if inspect.isawaitable(result) or inspect.iscoroutine(result)
        else result
    )


def find_behaviors(request):
    r_class = request.__class__
    behaviors = []
    for key, val in __behaviors__.items():
        if key == r_class or issubclass(r_class, key) or key == Any:
            behaviors = behaviors + val
    return behaviors


def find_notifications(request):
    r_class = request.__class__
    notifications = []
    for key, val in __notifications__.items():
        if key == r_class or issubclass(r_class, key) or key == Any:
            notifications = notifications + val
    return notifications


class Mediator:
    """Class of mediator as entry point to send requests and get responses"""

    handler_class_manager = default_handler_class_manager

    def __init__(self, handler_class_manager: Callable = None):
        if handler_class_manager:
            self.handler_class_manager = handler_class_manager

    def __before_send(
        self: Union["Mediator", GenericQuery[TResponse]],
        request: Optional[GenericQuery[TResponse]] = None,
    ):
        self1 = Mediator if not request else self
        request = request or self

        raise_if_request_none(request)

        notifications = find_notifications(request)

        handler = None
        if __handlers__.get(request.__class__):
            handler = __handlers__[request.__class__]
        elif __handlers__.get(request.__class__.__name__):
            handler = __handlers__[request.__class__.__name__]

        if not handler and notifications:
            return (self1, [], notifications)

        raise_if_handler_not_found(handler, request)

        handler_func = None
        handler_obj = None
        if inspect.isfunction(handler):
            handler_func = handler
        else:
            handler_obj = self1.handler_class_manager(handler)
            handler_func = handler_obj.handle

        behaviors = find_behaviors(request)
        behaviors.append(lambda r, next: handler_func(r))

        return (self1, behaviors, notifications)

    def __get_function(self, self1, target):
        target_func = None
        if inspect.isfunction(target):
            target_func = target
        else:
            target_obj = self1.handler_class_manager(target)
            target_func = target_obj.handle
        return target_func

    async def send_async(
        self: Union["Mediator", GenericQuery[TResponse]],
        request: Optional[GenericQuery[TResponse]] = None,
    ) -> Awaitable[TResponse]:
        """
        Send request in async mode and getting response

        Args:
        request (`object`): object of request class

        Returns:

        awaitable response

        """

        (self1, behaviors, notifications) = self.__before_send(request)

        beh_result = None
        if behaviors:

            async def start_func(i: int):
                beh_func = self.__get_function(self1, behaviors[i])
                return await __return_await__(
                    beh_func(request, lambda: start_func(i + 1))
                )

            beh_result = await start_func(0)

        for notification in notifications:
            n_func = self.__get_function(self1, notification)
            await __return_await__(n_func(request))

        return beh_result

    def send(
        self: Union["Mediator", GenericQuery[TResponse]],
        request: Optional[GenericQuery[TResponse]] = None,
    ) -> TResponse:
        """
        Send request in synchronous mode and getting response

        Args:
        request (`object`): object of request class

        Returns:

        response object or `None`

        """

        (self1, behaviors, notifications) = self.__before_send(request)

        beh_result = None
        if behaviors:

            def start_func(i: int):
                beh_func = self.__get_function(self1, behaviors[i])
                return beh_func(request, lambda: start_func(i + 1))

            beh_result = start_func(0)

        for notification in notifications:
            n_func = self.__get_function(self1, notification)
            n_func(request)

        return beh_result

    @staticmethod
    def clear():
        __handlers__.clear()
        __notifications__.clear()
        __behaviors__.clear()

    @staticmethod
    def register_handler(handler):
        """Append handler function or class to global handlers dictionary"""
        request_type = extract_request_type(handler, RequestType.HANDLER)
        if not __handlers__.get(request_type):
            __handlers__[request_type] = handler

    @staticmethod
    def register_notification(handler):
        """Append notification function or class to global notifications dictionary"""
        request_type = extract_request_type(handler, RequestType.NOTIFICATION)
        if not __notifications__.get(request_type):
            __notifications__[request_type] = []
        if not any(x == handler for x in __notifications__[request_type]):
            __notifications__[request_type].append(handler)

    @staticmethod
    def register_behavior(behavior):
        """Append behavior function or class to global behaviors dictionary"""
        request_type = extract_request_type(behavior, RequestType.BEHAVIOR)
        if not __behaviors__.get(request_type):
            __behaviors__[request_type] = []
        if not any(x == behavior for x in __behaviors__[request_type]):
            __behaviors__[request_type].append(behavior)

    @staticmethod
    def handler(handler):
        """Append handler function or class to global handlers dictionary"""
        Mediator.register_handler(handler)
        return handler

    @staticmethod
    def notification(handler):
        """Append handler function or class to global handlers dictionary"""
        Mediator.register_notification(handler)
        return handler

    @staticmethod
    def behavior(behavior):
        """Append behavior function or class to global behaviors dictionary"""
        Mediator.register_behavior(behavior)
        return behavior
