Bitswan: A tool for building Pipelines & Automations in Jupyter
===============================================

You can create a pipeline by defining 
1) A data source that you want to subscribe to
2) A pipeline body which defines data handling

You can find example pipelines in the [examples](./examples/) directory.

Installation
--------------

```
$ git clone git@github.com:bitswan-space/BitSwan.git
$ cd BitSwan
$ python3 -m venv venv
$ source venv/bin/activate
$ pip3 install -e ".[dev]"
```


Running pipelines
--------------------

You can run a pipeline with a simple command:

```
$ bitswan-cli examples/WebForms/main.ipynb
```

This pipeline will set up a Web Form on your localhost which will allow you to submit a form.


When developing web endpoints it can be helpful to instruct the pipeline to automatically restart if the source code changes.

```
$ bitswan-cli examples/WebForms/main.ipynb --watch
```


Creating Pipelines
--------------

First, before creating a pipeline, you should import all the libraries that you need while running your code.

You can import the BitSwan library like this and set your coding environment.
```
from bspump.jupyter import *
```

Defining pipeline is made by using `auto_pipeline()` function as seen in [example](./examples/AutoPipeline/main.ipynb).
```
auto_pipeline(
    source=lambda app, pipeline: bspump.kafka.KafkaSource(app, pipeline, "KafkaConnection"),
    sink=lambda app, pipeline: bspump.kafka.KafkaSink(app, pipeline, "KafkaConnection")
)
```

In general, everything that is defined before `auto_pipeline()` function will run only 
once and that is while setting up the pipeline.

Everything that is defined after `auto_pipeline()` function will run everytime an event triggers the pipeline.

`autopipeline()` has 3 arguments which define it `source`,`sink` and `name`

`source` is the data source that you want to subscribe to. Everytime an event occurs within the data source (in this case Kafka),
it will trigger the pipeline to perform its action. The result of any computation that is done after `auto_pipeline()` 
is sent to the data sink which is defined within the `sink` argument of the pipeline. 
Lastly `name` defines the name of the pipeline. `name` is optional.

One last thing. Before running a pipeline, define the special variable `event`. This variable will be sent to the pipeline
after the `auto_pipeline()` is called. This variable will be sent to the sink at the end of the pipeline.

And now you are all set!!!

Here we define the string manipulation. 
The pipeline returns a dictionary with capitalized letters in reversed order with spaces in between.
```
# load the dictionary from an event special variable
event = json.loads(event.decode("utf8"))

# capitalize our dicitonary
event["foo"] = event["foo"].upper()

# reverse order and add some spaces in between
event["foo"] = (" " * some_constant).join(reversed(list(event["foo"])))

# set the variable which will be sent to the sink
event = json.dumps(event).encode()
```
And that's it! The value of the `event` variable at the end of the notebook will be sent to the `sink`. 

[In another example we defined the Meme Generator!](examples/MemeGenerator/main.ipynb) 

### Quick Web Forms
You can also define a simple Web Form using `auto_pipeline`.
```
auto_pipeline(
    source=lambda app, pipeline: WebFormSource(app, pipeline, route="/", fields=[
        TextField("textfield", display="Hello"),
        FileField("textfile", display="Text")
    ]),
    sink=lambda app, pipeline: WebSink(app, pipeline)
)
```
All the supported web elements are:
`TextField`
`FileField`
`IntField`
`ChoiceField`
`CheckboxField`

Running Tests
----------------

You can find examples for automatically testing pipelines in the [testing examples](./examples/Testing) directory.

Run tests with the `--test` flag.

```
$ bitswan-cli examples/Testing/InspectError/main.ipynb --test

Running tests for pipeline Kafka2KafkaPipeline.

    ┌ Testing event:        b'foo'
    └ Outputs:              [b'FOO'] ✔

All tests passed for Kafka2KafkaPipeline.


Running tests for pipeline auto_pipeline_1.

    ┌ Testing event:        b'{"foo":"aaa"}'
    └ Outputs:              [b'{"foo": "A   A   A"}'] ✔

    ┌ Testing event:        b'{"foo":"aab"}'
    │ Probing after-upper.
    └ Outputs:              [b'{"foo": "B   A   A"}'] ✔

    ┌ Testing event:        b'{"foo":"cab"}'
    └ Outputs:              [b'{"foo": "B   A   C"}'] ✘
```

You can combine `--test` with `--watch` to automatically rerun tests whenever the source files change.


Licence
-------

Bitswan is open-source software, available under BSD 3-Clause License.

