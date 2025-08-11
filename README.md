Bitswan: A tool for building Pipelines & Automations in Jupyter
===============================================

You can find example pipelines in the [examples](./examples/) directory.

Installation
--------------

This library is part of the bitswan suite which is managed by the bitswan workspace cli.
You must first install the [bitswan workspaces](https://github.com/bitswan-space/bitswan-workspaces) cli before installing and using the bitswan notebooks cli.

```
$ git clone git@github.com:bitswan-space/BitSwan.git
$ cd BitSwan
$ curl -LsSf https://astral.sh/uv/install.sh | sh
$ uv venv
$ source .venv/bin/activate
$ uv pip install -e ".[dev]"
```

Running pipelines
--------------------

You can run a pipeline with a simple command:

```
$ bitswan notebook examples/WebForms/main.ipynb
```

When developing web endpoints it can be helpful to instruct the pipeline to automatically restart if the source code changes.

```
$ bitswan notebook examples/WebForms/main.ipynb --watch
```

Running Tests
----------------

You can find examples for automatically testing pipelines in the [testing examples](./examples/Testing) directory.

Run tests with the `--test` flag.

```
$ bitswan notebook examples/Testing/InspectError/main.ipynb --test

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

