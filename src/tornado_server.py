import json
import logging
import os

import pygame
import tornado.web
import tornado.websocket

import utils


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_COOKIE_NAME = "user"


connections = set()
logger = logging.getLogger("doorbell")


def _initialize(self, config, message_types):
    self.config = config
    self.message_types = message_types


def _get_current_user(self):
    return self.get_secure_cookie(USER_COOKIE_NAME)


def with_config_and_message_types(cls):
    cls.initialize = _initialize
    return cls


def login_required(methods=("get")):
    def decorator(cls):
        cls.get_current_user = _get_current_user
        for method_name in methods:
            method = getattr(cls, method_name)
            setattr(cls, method_name, tornado.web.authenticated(method))
        return cls
    return decorator


@with_config_and_message_types
class LoginHandler(tornado.web.RequestHandler):
    def get(self):
        template_context = dict(
            next_url=self.get_argument("next", default="/status"),
        )
        self.render(
            os.path.join(BASE_DIR, "template/login.html"),
            **template_context,
        )

    def post(self):
        password_ok = False
        try:
            password_ok = utils.verify_password(
                self.config.password_hash,
                self.get_argument("password")
            )
            if password_ok:
                self.set_secure_cookie(
                    USER_COOKIE_NAME,
                    self.get_argument("username")
                )
        except utils.VerificationError:
            pass

        if password_ok:
            next_url = self.get_argument("next_url")
            self.redirect(next_url)
        else:
            self.get()


@with_config_and_message_types
class WebSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        logger.info("got a connection...")
        connections.add(self)

    def on_message(self, message):
        message = json.loads(message)
        logger.info("message", message)
        message_type = message["type"]
        if message_type == self.message_types["request_volume"]:
            self.write_message({
                "type": self.message_types["receive_volume"],
                "volume": pygame.mixer.music.get_volume(),
            })
        elif message_type == self.message_types["update_volume"]:
            new_volume = message["volume"]
            logger.info(
                "new volume =",
                new_volume,
                "({})".format(str(type(new_volume)))
            )
            pygame.mixer.music.set_volume(new_volume)
            for client in connections:
                if client is not self:
                    client.write_message({
                        "type": self.message_types['receive_volume'],
                        "volume": new_volume,
                    })

    def on_close(self):
        connections.remove(self)

    # @override
    def write_message(self, message):
        super().write_message(json.dumps(message))


@login_required(["get"])
@with_config_and_message_types
class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        template_context = dict(
            message_types=self.message_types,
            bell_log=self._get_logs(),
            do_not_disturb_mode_is_on=utils.do_not_disturb_now(self.config),
            websocket_url="/websocket",
        )
        self.render(
            os.path.join(BASE_DIR, "template/status.html"),
            **template_context,
        )

    # TODO: Make this efficient for large log files!
    #       See https://stackoverflow.com/questions/7167008/
    def _get_logs(self, limit=40):
        # try:
        #     with open(os.path.join(BASE_DIR, "app.log")) as file:
        #         lines = file.readlines()
        # except OSError:
        #     lines = []
        # return reversed(lines[:-limit])
        return []


@login_required(["get"])
class TodosHandler(tornado.web.RequestHandler):
    todos_filepath = os.path.join(BASE_DIR, "todos.json")

    def get(self):
        with open(self.todos_filepath) as file:
            todos = file.read()
        template_context = dict(todos=todos)
        self.render(
            os.path.join(BASE_DIR, "template/todos.html"),
            **template_context,
        )

    def post(self):
        todos = json.loads(self.request.body.decode('utf-8'))
        with open(self.todos_filepath, "w") as file:
            json.dump(todos, file)


def start(config, message_types):
    initialization_kwargs = dict(
        config=config,
        message_types=message_types,
    )
    app = tornado.web.Application(
        [
            (r"/login", LoginHandler, initialization_kwargs),
            (r"/status", StatusHandler, initialization_kwargs),
            (r"/todos", TodosHandler),
            (r"/websocket", WebSocketHandler, initialization_kwargs),
        ],
        static_path=os.path.join(BASE_DIR, 'static'),
        static_url_prefix='/static/',
        login_url="/login",
        # https://www.grc.com/passwords.htm
        cookie_secret=config.cookie_secret,  # NOQA
    )
    app.listen(config.port)
    print(app, config.port, message_types)
