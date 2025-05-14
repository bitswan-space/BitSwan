import aiohttp.web
import os

from bspump.http_webchat.api.template_env import template_env
from bspump.http_webchat.server.app import WebChatResponse, WebChatWelcomeWindow, WebChatPromptForm, \
    WebChatResponseSequence, FormInput

base_dir = os.path.dirname(os.path.abspath(__file__))

# /api/welcome_message
async def get_welcome_message(request):
    fund_input = FormInput(
        label="Fond",
        name="fund_id",
        input_type="text",
        required=True
    )
    formfund = WebChatPromptForm(
        form_inputs=[fund_input],
        submit_api_call="/api/response_box"
    )
    welcome_message = WebChatWelcomeWindow(welcome_text="Hello, welcome to the odkupy calculation assistant. Please select the fond you would like to calculate odkupy for.", prompt_form=formfund, template_env=template_env)
    return aiohttp.web.Response(text=welcome_message.get_html(), content_type='text/html')

# /api/response_box
# what can I get as input?
async def get_web_chat_response(request):
    if request.method == 'POST':
        data = await request.post()
    else:
        data = request.query

    fund_id = data.get('fund_id')
    validation_date = data.get('validation_date')

    if fund_id:
        if fund_id == "123":
            return await get_response_123()
        elif fund_id == "12":
            return await get_response_12(request)
        else:
            fund_inputs = [
                FormInput(label="Validation Date", name="validation_date", input_type="date", required=True),
                FormInput(label="Closing Date", name="closing_date", input_type="date"),
                FormInput(label="Return Rate (%)", name="return_rate", input_type="number", step=0.01),
                FormInput(label="Closing Value", name="closing_value", input_type="number", step=0.01)
            ]
            form = WebChatPromptForm(
                form_inputs=fund_inputs,
                submit_api_call="/api/response_box"
            )
            webchat = WebChatResponse(
                input_html="I need more information",
                prompt_form=form,
                template_env=template_env,
            )
            return aiohttp.web.Response(text=webchat.get_html(), content_type='text/html')

    elif validation_date:
        webchat = WebChatResponse(input_html="Total valuation is 15000", template_env=template_env)
        return aiohttp.web.Response(text=webchat.get_html(), content_type='text/html')

    return aiohttp.web.json_response({"error": "Missing fund_id or validation_date"}, status=400)


async def get_response_123():
    response_sequence = WebChatResponseSequence([
        WebChatResponse(input_html="Calculating odkupy for Fund 123", template_env=template_env),
        WebChatResponse(input_html="Total valuation is", api_endpoint="https://run.mocky.io/v3/1e17cf34-ab78-40b9-8512-136e290a43c2", template_env=template_env),
        WebChatResponse(input_html="Please pick another fund for calculation.", template_env=template_env),
    ])

    rendered_html = response_sequence.get_html(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type='text/html')

# submit in form calls again response endpoint
# I should change it so it makes request to api and continues with sequence
async def get_response_12(request):
    fund_input = FormInput(
        label="Fond",
        name="fund_id",
        input_type="text",
        required=True
    )
    formfund = WebChatPromptForm(
        form_inputs=[fund_input],
        submit_api_call="/api/response_box"
    )

    fund_inputs = [
        FormInput(label="Validation Date", name="validation_date", input_type="date", required=True),
        FormInput(label="Closing Date", name="closing_date", input_type="date"),
        FormInput(label="Return Rate (%)", name="return_rate", input_type="number", step=0.01),
        FormInput(label="Closing Value", name="closing_value", input_type="number", step=0.01)
    ]
    form = WebChatPromptForm(
        form_inputs=fund_inputs,
        submit_api_call="/api/mock"
    )

    response_sequence = WebChatResponseSequence([
        WebChatResponse(input_html="Calculating odkupy for Fund 123", template_env=template_env),
        WebChatResponse(
            input_html="I need more information",
            prompt_form=form,
            template_env=template_env,
        ),
        WebChatResponse(input_html="Please pick another fund for calculation.", prompt_form=formfund, template_env=template_env)
    ])

    rendered_html = response_sequence.get_html(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type='text/html')