class MessageSourceModel():
    def __init__(self, content_source_path, content_source, is_relevant_path, is_relevant):
        self.__is_relevant_fnc = is_relevant
        self.__is_relevant_path = is_relevant_path
        self.__get_content = content_source
        self.__content_source_path = content_source_path

    def __get_is_relevant(self):
        try:
            return self.__is_relevant_fnc()
        except:
            raise Exception(
                f"Cannot read relevance from {self.__content_source_path}")
    is_relevant = property(__get_is_relevant)

    def __get_content_value(self):
        try:
            return self.__get_content()
        except:
            raise Exception(
                f"Cannot read value from {self.__content_source_path}")
    content = property(__get_content_value)

    def get_data(self):
        return {
            "is_relevant": self.__is_relevant_fnc(),
            "is_relevant_origin": self.__is_relevant_path,
            "content": self.__get_content(),
            "content_origin": self.__content_source_path,
        }

    def __repr__(self):
        rel_str = "O" if self.__is_relevant_fnc() else " "
        return f"{rel_str} {self.__get_content()}"
