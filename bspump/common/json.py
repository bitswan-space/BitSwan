import json
from ..abc.processor import Processor


class StdDictToJsonParser(Processor):
    """
    Description:

    |

    """

    def process(self, context, event):
        """
        Description:

        :return: ?

        |

        """
        return json.dumps(event)


class StdJsonToDictParser(Processor):
    """
    Description:

    |

    """

    def process(self, context, event):
        """
        Description:

        :return: ???

        |

        """
        return json.loads(event)


class DictToJsonBytesParser(Processor):
    """
    DictToJsonBytesParser transforms a dictionary to JSON-string encoded in bytes.
    The encoding charset can be specified in the configuration in `encoding` field.

    |

    """

    ConfigDefaults = {
        "encoding": "utf-8",
    }

    def __init__(self, app, pipeline, id=None, config=None):
        """
        Description: ..

        |

        """
        super().__init__(app, pipeline, id, config)
        self.Encoding = self.Config["encoding"]

    def process(self, context, event):
        """
        Description:

        :return: ??

        |

        """
        assert isinstance(event, dict)
        return json.dumps(event).encode(self.Encoding)
