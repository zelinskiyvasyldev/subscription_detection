import streamlit as st
from exa_py import Exa
from openai import OpenAI
import time
import pandas as pd
from io import StringIO
import json

st.set_page_config(page_title="Digital Goods Analyzer", layout="centered")

st.title("Digital Goods & Subscription Model Analyzer")

api_key = st.text_input("Enter your Exa API Key", type="password")

urls_input = st.text_area("Enter URLs (comma or newline separated)")

mode = st.radio("Choose mode:", ["Structured (exa_py SDK)", "Streaming (OpenAI client)"])

prompt_template = """Analyze and visit the following website URL to determine if it likely belongs to a platform providing digital goods or services and accepts credit card payments. Consider these factors:
- Presence of digital goods or services indicators (e.g., software downloads, subscription plans)
- Payment-related keywords (checkout, payment, pricing, subscribe, buy now, plans)
- Trust indicators (secure payment icons, SSL certificates, payment processor logos like Stripe or PayPal)
- Privacy Policy/Terms of Service: mentions of credit cards, payment methods, or financial data handling
- Evidence of transactions involving digital goods or services (e.g., app download links, mentions of in-app purchases, digital subscriptions)
- Exclude ecommerce websites and crypto websites
Type of Goods Sold: Specify whether the website sells Digital Goods, Physical Goods, or Both.
Subscription Payment Model: Indicate whether the website uses a subscription payment model (Yes/No).
Output Example must be like: Digital Goods, Yes
Analyze the following URL and only return the result as output

{url}
"""

def analyze_structured(exa, url):
    instructions = prompt_template.format(url=url)
    task_stub = exa.research.create_task(
        instructions=instructions,
        model="exa-research",
        output_infer_schema=True
    )
    start = time.time()
    timeout = 60
    while True:
        task = exa.research.poll_task(task_stub.id)
        if task.status == "completed":
            data = getattr(task, "data", {})
            return {
                "url": data.get("url", url),
                "typeOfGoodsSold": data.get("typeOfGoodsSold", ""),
                "subscriptionPaymentModel": data.get("subscriptionPaymentModel", "")
            }
        elif task.status == "failed":
            return {"url": url, "typeOfGoodsSold": "Error", "subscriptionPaymentModel": "Task failed"}
        elif time.time() - start > timeout:
            return {"url": url, "typeOfGoodsSold": "Timeout", "subscriptionPaymentModel": "Timeout"}
        time.sleep(1)

def analyze_streaming(client, url):
    prompt = prompt_template.format(url=url)
    messages = [{"role": "user", "content": prompt}]
    completion = client.chat.completions.create(
        model="exa-research",
        messages=messages,
        stream=True
    )
    full_response = ""
    for chunk in completion:
        delta = chunk.choices[0].delta
        if "content" in delta:
            text = delta.content
            full_response += text
            st.write(text, end="")
    # Try parse JSON out of the text
    try:
        json_start = full_response.find('{')
        json_obj = json.loads(full_response[json_start:])
        data = json_obj.get("data", {})
        return {
            "url": data.get("url", url),
            "typeOfGoodsSold": data.get("typeOfGoodsSold", ""),
            "subscriptionPaymentModel": data.get("subscriptionPaymentModel", "")
        }
    except Exception:
        return {"url": url, "typeOfGoodsSold": "ParseError", "subscriptionPaymentModel": ""}

if st.button("Analyze") and api_key and urls_input:
    urls = [u.strip() for u in urls_input.replace(",", "\n").split("\n") if u.strip()]
    results = []
    if mode == "Structured (exa_py SDK)":
        exa = Exa(api_key=api_key)
        for url in urls:
            with st.spinner(f"Analyzing {url}..."):
                result = analyze_structured(exa, url)
            st.json(result)
            results.append(result)
    else:
        client = OpenAI(base_url="https://api.exa.ai", api_key=api_key)
        for url in urls:
            st.write(f"### URL: {url}")
            with st.spinner("Streaming response..."):
                result = analyze_streaming(client, url)
            results.append(result)

    if results:
        df = pd.DataFrame(results)
        st.markdown("---")
        st.header("Summary Table")
        st.dataframe(df)

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button("Download CSV", csv_buffer.getvalue(), "digital_goods_analysis.csv", "text/csv")
else:
    st.info("Enter your API key and URLs, then click Analyze.")
