<template>
  <div
    class="container pa-3 d-flex flex-column justify-content-between fill-height"
  >
    <div class="messages-container pt-4">
      <div v-if="messages.length > 0" class="messages-list">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="mb-4"
          :class="msg.from === 'user' ? ' user-message text-end' : 'ia-message'"
        >
          <span
            :class="
              msg.from === 'user' ? 'bg-surface-light rounded-lg pa-4' : ''
            "
          >
            {{ msg.text }}
          </span>
        </div>
      </div>

      <div v-if="error" class="text-error">{{ error }}</div>
    </div>
    <div class="mt-3 input-container">
      <spinner v-if="isLoading" />
      <!-- Input de PDF oculto -->
      <input
        ref="fileInput"
        accept="application/pdf"
        class="d-none"
        :disabled="isLoading"
        type="file"
        @change="handleFileChange"
      >

      <!-- Input de texto -->
      <v-text-field
        v-model="input"
        append-icon="mdi-send"
        label="Escribe tu mensaje"
        @click:append="send"
        @dragover.prevent
        @drop.prevent="onDrop"
        @keyup.enter="send"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import spinner from '@/components/ui/spinner.vue'
  import axios from '@/plugins/axios'

  import { useOllamaStore } from '@/stores/ollama'

  const store = useOllamaStore()
  const input = ref('')
  const messages = computed(() => store.messages)
  const fileInput = ref<HTMLInputElement | null>(null)
  const isLoading = ref(false)
  const error = ref('')

  function onDrop (e: DragEvent) {
    const files = e.dataTransfer?.files
    if (files && files.length > 0) {
      uploadPdf(files[0])
    }
  }

  function handleFileChange (e: Event) {
    const target = e.target as HTMLInputElement
    const files = target.files
    if (files && files.length > 0) {
      uploadPdf(files[0])
    }
    if (target) target.value = ''
  }

  async function uploadPdf (file: File) {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await axios.post(
        'api/files_2',
        formData,
      )
      if (data.chunks) {
        for (const chunk of data.chunks as string[]) {
          store.addMessage({ from: 'ai', text: chunk })
        }
      }
    } catch (error_) {
      console.error('Error al dividir PDF:', error_)
    }
  }

  onMounted(async () => {
    store.connect()
  })

  // function send() {
  //   if (!input.value) return;
  //   store.sendMessage(input.value);
  //   input.value = "";
  // }

  const OLLAMA_URL = import.meta.env.VITE_OLLAMA_URL || 'http://localhost:11434'

  const _sendMesageToOllama = async (message: string) => {
    try {
      const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
        model: 'llama3',
        prompt: message,
        stream: true,
      })
      return response.data
    } catch (error) {
      console.error('Error al enviar el mensaje a Ollama:', error)
      return null
    }
  }
  // function send() {
  //   if (!input.value) return;
  //   let text = input.value;
  //   input.value = "";
  //   store.addMessage({
  //     from: "user",
  //     text: text,
  //   });
  //   sendMesageToOllama(text).then((response) => {
  //     if (response) {
  //       store.addMessage({
  //         from: "ai",
  //         text: response.response,
  //       });
  //     }
  //   });
  // }
  function send () {
    if (!input.value) return

    const text = input.value
    input.value = ''

    // Agregar mensaje del usuario
    store.addMessage({
      from: 'user',
      text,
    })

    // Inicializar mensaje del asistente
    let aiResponse = ''
    store.addMessage({
      from: 'ai',
      text: aiResponse,
    })

    // Referencia al mensaje recién agregado para ir actualizándolo
    const aiIndex = store.messages.length - 1

    error.value = ''
    sendMessageToOllamaStream(text, chunk => {
      aiResponse += chunk
      store.messages[aiIndex].text = aiResponse
    }).catch(() => {
      store.messages[aiIndex].text = ''
    })
  }

  const sendMessageToOllamaStream = async (
    prompt: string,
    onChunk: (text: string) => void,
  ) => {
    isLoading.value = true
    try {
      const response = await fetch(`${OLLAMA_URL}/api/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'llama3',
          prompt,
          stream: true,
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder('utf8')

      let fullText = ''

      if (!reader) throw new Error('sin lector')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })

        // Ollama envía múltiples objetos JSON por línea
        const lines = chunk.split('\n').filter(Boolean)

        for (const line of lines) {
          try {
            const json = JSON.parse(line)
            if (json.response) {
              fullText += json.response
              onChunk(json.response) // Emite fragmento
            }
          } catch (error_) {
            console.error('Error al parsear línea:', line, error_)
          }
        }
      }

      return fullText
    } catch (error_) {
      error.value = 'Error al comunicarse con la IA'
      throw error_
    } finally {
      isLoading.value = false
    }
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
</style>
<route lang="yaml">
meta:
  requiresAuth: false
</route>
