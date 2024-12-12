import pyjq
from bspump.abc.processor import Processor


class JQProcessor(Processor):
    """
    JQProcessor is a processor that uses JQ query language to transform data.
    """

    def __init__(self, app, pipeline, id=None, config=None, query=None):
        super().__init__(app, pipeline, id=id, config=config)
        self.Query = query or "{}".format(self.Config["query"])

    def process(self, context, event):
        return pyjq.first(self.Query, event)


# MockProcessor inherits from JQProcessor to avoid dependency on BSPump
class MockProcessor(JQProcessor):
    def __init__(self, app, pipeline, *args, **kwargs):
        self.Query = "Mock Query"


def test_jq():
    # Arrange
    processor = MockProcessor(None, None, None)
    processor.Query = '{"hi": (.foo * 5) }'
    event = {"foo": 3}

    # Act
    result_event = processor.process(None, event)

    # Assert
    assert result_event == {"hi": 15}


def test_multiple_jq():
    # Arrange
    processor = MockProcessor(None, None, None)
    processor.Query = (
        '{"result1": (.foo * 5), "result2": (.foo * 10), "result3": (.foo * 15) }'
    )
    event = {"foo": 3}

    # Act
    result_event = processor.process(None, event)

    # Assert
    assert result_event == {"result1": 15, "result2": 30, "result3": 45}


def test_concat_jq():
    # Arrange
    processor = MockProcessor(None, None, None)
    processor.Query = (
        '{"result1": (.value2 + .value3), "result2": (.value1 * .value4) }'
    )
    event = {"value1": 3, "value2": "hi", "value3": "!", "value4": 5}

    # Act
    result_event = processor.process(None, event)

    # Assert
    assert result_event == {"result1": "hi!", "result2": 15}


def test_typecast_jq():
    # Arrange
    processor = MockProcessor(None, None, None)
    processor.Query = '{"result1": (.value1 + (.value2|tonumber)) }'
    event = {"value1": 3, "value2": "2"}

    # Act
    result_event = processor.process(None, event)

    # Assert
    assert result_event == {"result1": 5}
