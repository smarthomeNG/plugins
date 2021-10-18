class MessageSourceProxy():
    def __init__(self, original_source, relevance_forcer):
        self.__original_source = original_source
        self.__relevance_forcer = relevance_forcer

    def __get_is_relevant(self):
        res = self.__relevance_forcer()
        if res is None:
            return self.__original_source.is_relevant
        return res
    is_relevant = property(__get_is_relevant)

    def __get_content_value(self):
        return self.__original_source.content
    content = property(__get_content_value)

    def get_data(self):
        return {
            "is_relevant": self.is_relevant,
            "is_relevant_origin": self.__original_source.__is_relevant_path,
            "content": self.content,
            "content_origin": self.__original_source.__content_source_path,
        }

    def __repr__(self):
        res = self.__relevance_forcer()
        if res is None:
            rel_str = "O" if self.is_relevant else " "
        else:
            rel_str = "P" if res else "-"
                    
        return f"{rel_str} {self.content}"
