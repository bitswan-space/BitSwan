import abc


class Module(abc.ABC):
    """
    Abstract class for ASAB modules.

    Modules are registered at the module registry `asab.Application.Modules`, managed by an application object.
    Module can be loaded by ASAB and typically provides one or more Service objects.

    Every module provides asynchronous methods `initialize()` and `finalize()`.
    `initialize()` is called in the very beginning of the run-time,
    `finalize()` in the gentle shut-down of the application.

    Examples:

    Recommended structure of the ASAB module:

    ```
    my_module/
            - __init__.py
            - my_service.py
    ```

    Content of `__init__.py`:

    ```python title="__init__.py"
    import bspump.asab as asab
    from .my_service import MyService

    # Extend ASAB configuration defaults
    asab.Config.add_defaults({
            'my_module': {
                    'foo': 'bar'
            }
    })

    class MyModule(asab.Module):
            def __init__(self, app):
                    super().__init__(app)
                    self.service = MyService(app, "MyService")
    ```

    And this is how the module is loaded:

    ```python
    from mymodule import MyModule
    ...
    app.add_module(MyModule)
    ```

    """

    def __init__(self, app):
        pass

    # Lifecycle

    async def initialize(self, app):
        """
        This method is called when the Module is initialized. It can be overridden by an user.

        Args:
                app (asab.Application): Reference to ASAB application.
        """
        pass

    async def finalize(self, app):
        """
        This method is called when the Module is finalized, e.g., during application `exit-time`. It can be overridden by an user.

        Args:
                app (asab.Application): Reference to ASAB application.
        """
        pass
