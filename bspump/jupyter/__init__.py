def vscode_secrets_fixme():
    from IPython import get_ipython

    ipy = get_ipython()
    if not ipy:
        return
    import re
    import os

    if "IPKernelApp" in ipy.config or "VSCODE_PID" in os.environ:
        uri = ipy.get_parent()["metadata"]["cellId"]
        match_ = re.match(r"vscode-notebook-cell://[^/]+(/.*?)/[^/]+\.ipynb", uri)
        if match_:
            cleaned_path = match_.group(1) + "/"
            os.chdir(cleaned_path)


try:
    vscode_secrets_fixme()
except Exception:
    pass

from .jupyter import (
    deploy,
    init_bitswan_jupyter,
    sample_events,
    register_app_post_init,
    register_connection,
    retrieve_sample_events,
    register_lookup,
    new_pipeline,
    end_pipeline,
    register_source,
    register_processor,
    register_generator,
    register_sink,
    step,
    async_step,
    App,
    bitswan_auto_pipeline,
    auto_pipeline,
    bitswan_test_mode,
    add_test_probe,
    bitswan_test_probes,
    bitswan_tested_pipelines,
)

__all__ = [
    "deploy",
    "init_bitswan_jupyter",
    "sample_events",
    "register_app_post_init",
    "register_connection",
    "retrieve_sample_events",
    "register_lookup",
    "new_pipeline",
    "end_pipeline",
    "register_source",
    "register_processor",
    "register_generator",
    "register_sink",
    "step",
    "async_step",
    "App",
    "auto_pipeline",
    "bitswan_auto_pipeline",
    "bitswan_test_mode",
    "add_test_probe",
    "bitswan_test_probes",
    "bitswan_tested_pipelines",
]
