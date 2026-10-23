# Friction Log – Household Ops

> This log records every meaningful obstacle encountered during the hackathon build.
> Honest friction logs earn a 10% judging bonus and help Amazon improve their tools.
> Update this as you build — do not write it all at the end.

**Builder:** [Your Name]  
**Hackathon:** Amazon Alexa+ Hackathon 2026  
**Track:** Alexa+ (MCP Add-on)  
**Period:** October 2026

---

## Entry Template

```
### Entry N – [Short Title]
- **Task attempted:** 
- **Steps taken:** 
- **Expected result:** 
- **Actual result:** 
- **Severity:** low | medium | high
- **Workaround used:** 
- **Suggestion for Amazon:** 
```

---

## Entries

### Entry 1 – MCP Python SDK Version Discovery

- **Task attempted:** Find which `mcp` package version supports the 2025-11-25 spec with Streamable HTTP transport.
- **Steps taken:** Ran `pip install mcp[cli]` which installed the latest version. Then checked the changelog and tested `transport="streamable-http"` in `mcp.run()`.
- **Expected result:** The README or PyPI page clearly stating which version supports which spec version and transport.
- **Actual result:** Had to cross-reference the GitHub changelog, the SDK README, and the MCP spec page separately to confirm compatibility. No single source of truth.
- **Severity:** medium
- **Workaround used:** Tested with MCP Inspector — if tools appeared, transport was working.
- **Suggestion for Amazon:** Add a compatibility matrix to the Alexa+ hackathon docs page: `mcp` version ↔ spec version ↔ transport name. One table would save builders an hour.

---

### Entry 2 – Bedrock Model Access Region Availability

- **Task attempted:** Enable Claude 3.5 Haiku model access in Bedrock to power the demo backend.
- **Steps taken:** Navigated to Bedrock console → Model access → selected Anthropic Claude 3.5 Haiku → submitted.
- **Expected result:** Instant access, as documented.
- **Actual result:** Model availability varies by region. The console does not prominently warn you if you are in a region where a model is unavailable until after you try to invoke it.
- **Severity:** medium
- **Workaround used:** Switched to `us-east-1` (N. Virginia) which had full model availability.
- **Suggestion for Amazon:** Show model regional availability directly on the Model Access page before submission, not only in the error message at inference time. A small flag icon next to unavailable models in non-qualifying regions would save significant debugging time.

---

### Entry 3 – Alexa AI CLI Onboarding Documentation

- **Task attempted:** Register the MCP server as an Alexa+ Add-on using the Alexa AI CLI.
- **Steps taken:** Searched developer.amazon.com for "Create an MCP Add-on". Found the page. Ran `alexa-ai configure` and `alexa-ai new mcp`.
- **Expected result:** Clear, end-to-end guide with exact CLI flags and what to expect after `alexa-ai deploy`.
- **Actual result:** The docs describe the flow but leave gaps: what confirmation appears after deploy, how to verify the add-on is live, and what happens if you redeploy with changed tool names.
- **Severity:** medium
- **Workaround used:** Used MCP Inspector and the Bedrock demo path to validate tool correctness independently of the Alexa+ add-on.
- **Suggestion for Amazon:** Add a "verify your deployment" section to the CLI docs: what a successful deploy output looks like, how to list deployed add-ons, and a simple `alexa-ai test` command that calls your server's tool list and confirms Alexa+ can reach it.

---

### Entry 4 – Public HTTPS URL Requirement

- **Task attempted:** Get a public HTTPS endpoint for the MCP server so the Alexa+ add-on config accepts it.
- **Steps taken:** Tried ngrok (requires account now), tried cloudflared, then deployed to Render.
- **Expected result:** Simple local tunnel with stable URL during development.
- **Actual result:** ngrok free tier gives a random URL that changes every restart. Cloudflared works but documentation for Windows setup is thin. Render free tier has cold-start latency that can cause the first tool call to time out.
- **Severity:** low
- **Workaround used:** Deployed to Render and added a health-ping keep-alive.
- **Suggestion for Amazon:** Consider providing a temporary, stable tunnel service (like AWS CloudShell with port forwarding, or a `alexa-ai tunnel` sub-command) so hackathon builders can develop locally without deploying to a host.

---

### Entry 5 – FastMCP `mcp.run()` ASGI Integration

- **Task attempted:** Run the FastMCP server using `uvicorn` alongside FastAPI for the demo backend.
- **Steps taken:** Called `mcp.run(transport="streamable-http")` — it starts its own internal server. Tried to import `mcp.app` to mount it into FastAPI.
- **Expected result:** A clean way to embed the MCP server as an ASGI sub-application inside FastAPI.
- **Actual result:** FastMCP creates its own Starlette/ASGI app internally. The mounting path is not documented clearly; had to read the FastMCP source to find the right attribute.
- **Severity:** low
- **Workaround used:** Ran MCP server and FastAPI backend as two separate processes — which is actually cleaner for the demo (shows two distinct services).
- **Suggestion for Amazon / MCP team:** Document how to embed `FastMCP` as an ASGI sub-app (e.g. `app.mount("/mcp", mcp.get_asgi_app())`). A one-liner example in the README would prevent 30 minutes of source-diving.

---

## Summary

| # | Title | Severity | Resolved? |
|---|-------|----------|-----------|
| 1 | SDK version discovery | Medium | ✅ via Inspector |
| 2 | Bedrock region availability | Medium | ✅ switched region |
| 3 | Alexa AI CLI docs gaps | Medium | ⚠️ workaround only |
| 4 | Public HTTPS requirement | Low | ✅ Render |
| 5 | FastMCP ASGI mounting | Low | ✅ separate processes |

**Overall developer experience:** Positive. The MCP spec and Python SDK are well-designed and the tool-calling pattern is intuitive. The biggest gap is documentation for the Alexa-specific onboarding steps (CLI and add-on lifecycle). The foundation is solid — the rough edges are mostly in the docs, not the APIs.
