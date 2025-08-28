<template>
  <div
    class="container pa-3 d-flex flex-column justify-content-between fill-height"
  >
    <div ref="messagesContainer" class="messages-container pt-4">
      <div v-if="messages.length > 0" class="messages-list">
        <template v-for="(msg, index) in messages" :key="index">
          <div
            class="mb-1 d-flex"
            :class="
              msg.from === 'user'
                ? ' user-message text-end justify-end'
                : 'ia-message'
            "
          >
            <span
              v-if="msg.from === 'user'"
              class="bg-surface-light rounded-lg pa-4"
            >
              {{ msg.text }}
            </span>
            <div
              v-else
              class="markdown-body"
              v-html="renderMarkdown(msg.text)"
            />
            <!-- Opcional: fuentes del RAG (si guardaste meta en el mensaje) -->
          </div>
          <v-tooltip interactive>
            <template #activator="{ props: activatorProps }">
              <v-icon-btn
                v-if="msg.meta?.chunks?.length"
                icon="mdi-information-outline"
                v-bind="activatorProps"
              />
            </template>
            <strong>Fuentes:</strong>
            <ul v-if="msg.meta?.chunks?.length" class="pl-4">
              <li v-for="(s, i) in msg.meta.chunks" :key="i">
                {{ s.filename || "documento" }}
                <span v-if="s.topic"> — {{ s.topic }}</span>
                <span v-if="s.module"> ({{ s.module }})</span>
              </li>
            </ul>
          </v-tooltip>
        </template>
      </div>

      <div v-if="error">
        <span
          class="text-on-surface bg-error elevation-4 rounded py-2 px-6 mr-3"
        >
          {{ error }}
        </span>
      </div>
    </div>
    <div class="mt-3 input-container">
      <spinner v-if="isLoading" />
      <!-- Input de texto -->
      <v-text-field
        v-model="input"
        :append-icon="isLoading ? 'mdi-stop' : 'mdi-send'"
        label="Escribe tu mensaje"
        @click:append="isLoading ? cancel() : send()"
        @keyup.enter="send"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import spinner from "@/components/ui/spinner.vue";
import axios from "@/plugins/axios";
import { useOllamaStore } from "@/stores/ollama";
import { renderMarkdown } from "@/utils/md";
import {
  consumeNdjsonStream,
  type MetaEvent,
  type OllamaChunk,
} from "@/utils/ndjsonStream";
// 👇 controlador global de cancelación
let controller: AbortController | null = null;
const messagesContainer = ref<HTMLElement | null>(null);
const store = useOllamaStore();
const input = ref("");
const messages = computed(() => store.messages);
const fileInput = ref<HTMLInputElement | null>(null);
const isLoading = ref(false);
const error = ref("");

function appendToMessage(index: number, chunk: string) {
  if (!store.messages[index]) return;
  store.messages[index].text = (store.messages[index].text || "") + chunk;
}

function updateMessageMeta(index: number, meta: any) {
  if (!store.messages[index]) return;
  store.messages[index].meta = meta;
}
onMounted(async () => {
  store.connect();
});
async function send() {
  if (!input.value.trim()) return;

  // 1) Mensaje del usuario
  const userText = input.value;
  input.value = "";
  store.addMessage({ from: "user", text: userText });

  // 2) Placeholder del asistente (iremos rellenando)
  store.addMessage({ from: "ai", text: "" });
  const aiIndex = store.messages.length - 1;

  error.value = "";
  isLoading.value = true;

  // 3) Cancelación
  controller?.abort();
  controller = new AbortController();

  try {
    const res = await fetch(`http://localhost:8000/api/chat_rag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: userText }),
      signal: controller.signal,
    });

    let finished = false;

    await consumeNdjsonStream(res, {
      onMeta(meta: MetaEvent) {
        // Guarda fuentes/meta en el mensaje IA
        if (typeof (store as any).updateMessageMeta === "function") {
          (store as any).updateMessageMeta(aiIndex, meta);
        } else {
          updateMessageMeta(aiIndex, meta);
        }
      },
      async onToken(t: string) {
        // Añade token y autoscroll
        if (typeof (store as any).appendToMessage === "function") {
          (store as any).appendToMessage(aiIndex, t);
        } else {
          appendToMessage(aiIndex, t);
        }
        await nextTick();
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop =
            messagesContainer.value.scrollHeight;
        }
      },
      onErrorLine(raw: string) {
        console.warn("Línea NDJSON no JSON:", raw);
      },
      onDone(_stats?: OllamaChunk) {
        finished = true;
      },
    });

    if (!finished) {
      console.warn("Stream finalizado sin 'done:true'");
    }
  } catch (error_: any) {
    if (error_.name !== "AbortError") {
      error.value = error_?.message || "Error de red";
    }
  } finally {
    isLoading.value = false;
    controller = null;
  }
}

function cancel() {
  controller?.abort();
  controller = null;
  isLoading.value = false;
}
</script>
<style lang="scss" scoped>
.container {
  max-width: 1200px;
  max-height: calc(100vh - 100px);
  margin: 0 auto;
  .messages-container {
    flex: 1;
    overflow-y: auto;
  }
  .user-message {
    max-width: 66%;
    margin-left: auto;
  }
}

.markdown-body {
  white-space: normal;
  line-height: 1.55;
}
.markdown-body pre {
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
}
.markdown-body code {
  padding: 0 4px;
}
</style>
<route lang="yaml">
meta:
  requiresAuth: false
</route>
