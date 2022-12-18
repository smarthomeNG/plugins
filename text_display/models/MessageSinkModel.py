from .MessageSourceModel import MessageSourceModel


class MessageSinkModel():
    def __init__(self, default_value, message_ring_reader, tick_time_hint = 3):
        self.__default_value = default_value
        self.__reader = message_ring_reader
        self.__tick_time_hint = tick_time_hint

    def tick(self):
        reader_result = self.__reader.read_next()
        if(reader_result is None):
            return self.__default_value
        else:
            return reader_result.content

    def has_relevant_messages(self):
        return self.__reader.has_relevant_messages()

    def introspect(self):
        return f"MessageSinkModel, based on: {self.__reader.introspect()}"

    def dump(self):
        return self.__reader.dump()

    def reset(self):
        self.__reader.reset()

    def __get_reader(self):
        return self.__reader
    reader = property(__get_reader)

    def __get_tick_time_hint(self):
        return self.__tick_time_hint
    tick_time_hint = property(__get_tick_time_hint)