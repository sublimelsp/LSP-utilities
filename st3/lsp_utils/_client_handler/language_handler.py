from ..api_wrapper_interface import ApiWrapperInterface
from ..server_resource_interface import ServerStatus
from .interface import ClientHandlerInterface
from LSP.plugin import ClientConfig
from LSP.plugin import LanguageHandler
from LSP.plugin import Notification
from LSP.plugin import read_client_config
from LSP.plugin import Request
from LSP.plugin import Response
from LSP.plugin.core.typing import Any, Callable, Dict, Optional
import sublime

__all__ = ['ClientHandler']


class ApiWrapper(ApiWrapperInterface):
    def __init__(self, client):
        self.__client = client

    # --- ApiWrapperInterface -----------------------------------------------------------------------------------------

    def on_notification(self, method: str, handler: Callable[[Any], None]) -> None:
        self.__client.on_notification(method, handler)

    def on_request(self, method: str, handler: Callable[[Any, Callable[[Any], None]], None]) -> None:
        def on_response(params, request_id):
            handler(params, lambda result: send_response(request_id, result))

        def send_response(request_id, result):
            self.__client.send_response(Response(request_id, result))

        self.__client.on_request(method, on_response)

    def send_notification(self, method: str, params: Any) -> None:
        self.__client.send_notification(Notification(method, params))

    def send_request(self, method: str, params: Any, handler: Callable[[Any, bool], None]) -> None:
        self.__client.send_request(
            Request(method, params), lambda result: handler(result, False), lambda result: handler(result, True))


class ClientHandler(LanguageHandler, ClientHandlerInterface):

    # --- LanguageHandler handlers ------------------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.package_name.lower()

    @classmethod
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        return cls.get_additional_variables()

    @property
    def config(self) -> ClientConfig:
        settings, filepath = self.read_settings()
        settings_dict = {}
        for key, default in self.get_default_settings_schema().items():
            settings_dict[key] = settings.get(key, default)
        if self.manages_server():
            can_enable = self.get_server() is not None
        else:
            can_enable = True
        enabled = settings_dict.get('enabled', True) and can_enable
        settings_dict['enabled'] = enabled
        if not settings_dict['command']:
            settings_dict['command'] = self.get_command()
        return read_client_config(self.name, settings_dict, filepath)

    @classmethod
    def on_start(cls, window: sublime.Window) -> bool:
        if cls.manages_server():
            server = cls.get_server()
            return server != None and server.get_status() == ServerStatus.READY
        message = cls.is_allowed_to_start(window)
        if message:
            window.status_message('{}: {}'.format(cls.package_name, message))
            return False
        return True

    def on_initialized(self, client) -> None:
        self.on_ready(ApiWrapper(client))

    # --- ClientHandlerInterface --------------------------------------------------------------------------------------

    @classmethod
    def setup(cls) -> None:
        super().setup()
        if cls.manages_server():
            server = cls.get_server()
            if server and server.needs_installation():
                server.install_or_update_async()

    @classmethod
    def get_default_settings_schema(cls) -> Dict[str, Any]:
        return {
            'command': [],
            'env': {},
            'experimental_capabilities': {},
            'initializationOptions': {},
            'languages': [],
            'settings': {},
        }

    @classmethod
    def get_storage_path(cls) -> str:
        return cls.storage_path()

    # --- Internals ---------------------------------------------------------------------------------------------------

    def __init__(self):
        super().__init__()
        # Calling setup() also here as this might run before `plugin_loaded`.
        # Will be a no-op if already ran.
        # See https://github.com/sublimelsp/LSP/issues/899
        self.setup()
