Bitswan: A tool for building Pipelines & Automations in Jupyter
===============================================

Bitswan library is developers tool for creating real-time event parsing using Python.
You can create pipeline simply by defining 
1) Data source that you want to subscribe to
2) Pipeline body which defines parsing of data

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

Creating Pipelines
--------------

Defining pipeline is made by using `auto_pipeline()` function as seen in [example](./examples/AutoPipeline/main.ipynb).
```
auto_pipeline(
    source=lambda app, pipeline: bspump.kafka.KafkaSource(app, pipeline, "KafkaConnection"),
    sink=lambda app, pipeline: bspump.kafka.KafkaSink(app, pipeline, "KafkaConnection")
)
```

`autopipeline()` has 3 arguments which define it `source`,`sink` and `name`

`source` is data source that you want to subscribe to. Everytime an event occurs within data source (in this case Kafka),
it will trigger pipeline to perform its action. The result is sent to data sink which is defined within `sink` argument  of
the pipeline. Lastly `name` defines the name of the pipeline. `name` is optional.

One last thing. Before running pipeline, define special variable `event`. This variable will be sent to the pipeline
after the `auto_pipeline()` is called. This variable will also be sent to the sink at the end of the pipeline.

And now you are all set!!!

Everytime an event occurs, it will automatically perform code that is defined after `auto_pipeline()`.

### Other pipeline features
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

### Defining pipeline using decorator
In case you do not want to use `auto_pipeline` function, you can define pipeline by using Python decorators 
[example](examples/WebForms/main.ipynb). 

1) Firstly define the pipeline start by using `new_pipeline()` function.
2) Define the data source using `@register_source` decorator
    ```
    @register_source
    def source(app, pipeline):
        return WebFormSource(app, pipeline, route="/", fields=[
            TextField("foo", display="Foo"),
            TextField("la", readonly=True, default="laa"),
            IntField("n"),
            TextField("bar", hidden=True),
            ChoiceField("lol", choices=["a","b","c"]),
            CheckboxField("checkbox"),
        ])
    ```
3) Define behaviour of pipeline by using decorator `@async_step` and `@step` for asynchronous and synchronous steps.
4) Define the data sink of pipeline using `@register_sink` decorator
5) Lastly define the end of the pipeline using `end_pipeline()`

Running pipelines
--------------------

You can run a pipeline with a simple command:

```
$ bitswan-cli examples/WebForms/main.ipynb
```

For example this pipeline will set up the Web Form on your localhost which will allow you to submit a form.

Pipelines can be also deployed using IDE. So far we have Visual Studio Code Extension. [Check it out!](https://marketplace.visualstudio.com/items?itemName=LibertyAcesLtd.bitswan)

When developing web endpoints it can be helpful to instruct the pipeline to automatically restart if the source code changes.

```
$ bitswan-cli examples/WebForms/main.ipynb --watch
```

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

