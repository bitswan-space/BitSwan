import os

import aiohttp.web

from bspump.http_webchat.server.app import WebChat, WebChatTemplateEnv, register_endpoint, _registered_endpoints
from bspump.http_webchat.server.app import (
    WebChatResponse,
    WebChatWelcomeWindow,
    WebChatPromptForm,
    WebChatResponseSequence,
    FormInput,
)

base_dir = os.path.dirname(os.path.abspath(__file__))

# First we must create the template env
template_env = WebChatTemplateEnv(
    os.path.abspath(os.path.join(base_dir, "templates"))
).get_jinja_env()

# Then we define the endpoints


# /api/welcome_message
async def get_welcome_message(request):
    fund_input = FormInput(
        label="Fond", name="fund_id", input_type="text", required=True
    )
    fund_form = WebChatPromptForm(
        form_inputs=[fund_input], submit_api_call="/api/response_box"
    )
    welcome_message = WebChatWelcomeWindow(
        welcome_text="Hello, welcome to the odkupy calculation assistant. Please select the fond you would like to calculate odkupy for.",
        prompt_form=fund_form,
        endpoint_route="/api/welcome_message",
    )
    return aiohttp.web.Response(
        text=welcome_message.get_html(template_env), content_type="text/html"
    )


# /api/response_box -> routing endpoint
async def get_web_chat_response(request):
    if request.method == "POST":
        data = await request.post()
    else:
        data = request.query

    fund_id = data.get("fund_id")
    validation_date = data.get("validation_date")

    if fund_id:
        # example with endpoint request
        if fund_id == "123":
            return aiohttp.web.Response(
                text=WebChatResponse(
                    input_html="Total valuation is",
                    api_endpoint="https://run.mocky.io/v3/1e17cf34-ab78-40b9-8512-136e290a43c2",
                ).get_html(template_env),
                content_type="text/html",
            )
        # sequence example
        elif fund_id == "12":
            return await get_response_12(request)
        else:
            return aiohttp.web.Response(
                text=WebChatResponse(input_html="Total valuation is 15000").get_html(
                    template_env
                ),
                content_type="text/html",
            )

    # additional form
    elif validation_date:
        webchat_response = WebChatResponse(input_html="Total valuation is 15000")
        return aiohttp.web.Response(
            text=webchat_response.get_html(template_env), content_type="text/html"
        )

    return aiohttp.web.json_response(
        {"error": "Missing fund_id or validation_date"}, status=400
    )


async def get_response_12(request):
    fund_input = FormInput(
        label="Fond", name="fund_id", input_type="text", required=True
    )
    first_fund_form = WebChatPromptForm(
        form_inputs=[fund_input], submit_api_call="/api/response_box"
    )

    fund_inputs = [
        FormInput(
            label="Validation Date",
            name="validation_date",
            input_type="date",
            required=True,
        ),
        FormInput(label="Closing Date", name="closing_date", input_type="date"),
        FormInput(
            label="Return Rate (%)", name="return_rate", input_type="number", step=0.01
        ),
        FormInput(
            label="Closing Value", name="closing_value", input_type="number", step=0.01
        ),
    ]
    second_fund_form = WebChatPromptForm(
        form_inputs=fund_inputs, submit_api_call="/api/mock"
    )

    response_sequence = WebChatResponseSequence(
        [
            WebChatResponse(input_html="Calculating odkupy for Fund 123"),
            WebChatResponse(
                input_html="I need more information",
                prompt_form=second_fund_form,
            ),
            WebChatResponse(
                input_html="Please pick another fund for calculation.",
                prompt_form=first_fund_form,
            ),
        ]
    )

    rendered_html = response_sequence.get_html(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type="text/html")


if __name__ == "__main__":
    register_endpoint("/api/welcome_message", get_welcome_message)
    register_endpoint("/api/response_box", get_web_chat_response)
    print(_registered_endpoints)
    webchat = WebChat(welcome_message_api="/api/welcome_message", prompt_response_api="/api/response_box")
