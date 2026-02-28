const chatLog = document.getElementById("chatLog");
const chatForm = document.getElementById("chatForm");
const promptInput = document.getElementById("promptInput");
const modelInput = document.getElementById("modelInput");
const streamInput = document.getElementById("streamInput");
const clearBtn = document.getElementById("clearBtn");
const statusText = document.getElementById("statusText");

const conversation = [];

function makeId(prefix) {
  const uuid = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${uuid}`;
}

function normalizeContent(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part?.type === "text") return part.text ?? "";
        return JSON.stringify(part);
      })
      .join(" ");
  }
  if (content && typeof content === "object") {
    if (typeof content.text === "string") return content.text;
    return JSON.stringify(content);
  }
  return "";
}

class PuterOpenAICompat {
  constructor(options = {}) {
    this.defaultModel = options.defaultModel ?? "gpt-4o-mini";
    this.chat = {
      completions: {
        create: (params) => this.createChatCompletion(params),
      },
    };
  }

  async createChatCompletion(params = {}) {
    if (!globalThis.puter?.ai?.chat) {
      throw new Error("puter.js was not found. Ensure https://js.puter.com/v2/ is loaded.");
    }

    const model = params.model ?? this.defaultModel;
    const stream = Boolean(params.stream);
    const prompt = this.messagesToPrompt(params.messages ?? []);

    if (stream) {
      const upstreamStream = await puter.ai.chat(prompt, { model, stream: true });
      return this.toOpenAIStream(upstreamStream, model);
    }

    const upstream = await puter.ai.chat(prompt, { model });
    const text = this.extractText(upstream);
    return this.toOpenAICompletion(model, text);
  }

  messagesToPrompt(messages) {
    if (!Array.isArray(messages) || messages.length === 0) {
      throw new Error("`messages` must be a non-empty array.");
    }

    return messages
      .map((message) => {
        const role = message?.role ?? "user";
        const content = normalizeContent(message?.content);
        return `${role}: ${content}`;
      })
      .join("\n");
  }

  extractText(payload) {
    if (typeof payload === "string") return payload;
    if (typeof payload?.text === "string") return payload.text;
    if (typeof payload?.message?.content === "string") return payload.message.content;
    if (Array.isArray(payload?.message?.content)) {
      return payload.message.content.map((part) => normalizeContent(part)).join(" ");
    }
    return JSON.stringify(payload);
  }

  extractStreamText(chunk) {
    if (typeof chunk === "string") return chunk;
    if (typeof chunk?.text === "string") return chunk.text;
    if (typeof chunk?.message?.content === "string") return chunk.message.content;
    if (typeof chunk?.delta?.content === "string") return chunk.delta.content;
    return "";
  }

  toOpenAICompletion(model, text) {
    return {
      id: makeId("chatcmpl"),
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: text },
          finish_reason: "stop",
        },
      ],
      usage: {
        prompt_tokens: null,
        completion_tokens: null,
        total_tokens: null,
      },
    };
  }

  toOpenAIStream(upstreamStream, model) {
    const completionId = makeId("chatcmpl");
    const created = Math.floor(Date.now() / 1000);
    const self = this;

    return (async function* streamGenerator() {
      for await (const chunk of upstreamStream) {
        const text = self.extractStreamText(chunk);
        if (!text) continue;

        yield {
          id: completionId,
          object: "chat.completion.chunk",
          created,
          model,
          choices: [
            {
              index: 0,
              delta: { content: text },
              finish_reason: null,
            },
          ],
        };
      }

      yield {
        id: completionId,
        object: "chat.completion.chunk",
        created,
        model,
        choices: [
          {
            index: 0,
            delta: {},
            finish_reason: "stop",
          },
        ],
      };
    })();
  }
}

globalThis.PuterOpenAICompat = PuterOpenAICompat;

const openai = new PuterOpenAICompat({
  defaultModel: modelInput.value,
});

function setStatus(text, isError = false) {
  statusText.textContent = text;
  statusText.classList.toggle("error", isError);
}

function addMessage(role, content = "") {
  const row = document.createElement("article");
  row.className = `msg ${role}`;

  const roleTag = document.createElement("span");
  roleTag.className = "role";
  roleTag.textContent = role;

  const body = document.createElement("p");
  body.className = "body";
  body.textContent = content;

  row.appendChild(roleTag);
  row.appendChild(body);
  chatLog.appendChild(row);
  chatLog.scrollTop = chatLog.scrollHeight;

  return body;
}

function resetConversation() {
  conversation.length = 0;
  chatLog.innerHTML = "";
  setStatus("Conversation cleared.");
}

clearBtn.addEventListener("click", resetConversation);

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  const model = modelInput.value.trim() || "gpt-4o-mini";
  openai.defaultModel = model;

  conversation.push({ role: "user", content: prompt });
  addMessage("user", prompt);
  promptInput.value = "";
  promptInput.focus();

  const assistantBody = addMessage("assistant", "");
  chatForm.querySelector("button[type=submit]").disabled = true;
  setStatus("Generating response...");

  try {
    if (streamInput.checked) {
      const stream = await openai.chat.completions.create({
        model,
        messages: conversation,
        stream: true,
      });

      let assembled = "";
      for await (const chunk of stream) {
        const delta = chunk?.choices?.[0]?.delta?.content ?? "";
        if (!delta) continue;
        assembled += delta;
        assistantBody.textContent = assembled;
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      conversation.push({ role: "assistant", content: assembled });
    } else {
      const completion = await openai.chat.completions.create({
        model,
        messages: conversation,
      });
      const answer = completion?.choices?.[0]?.message?.content ?? "";
      assistantBody.textContent = answer;
      conversation.push({ role: "assistant", content: answer });
    }

    setStatus("Done.");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    assistantBody.textContent = `[error] ${message}`;
    setStatus(message, true);
  } finally {
    chatForm.querySelector("button[type=submit]").disabled = false;
  }
});
