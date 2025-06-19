<template>
  <v-container>
    <h2 class="mb-4">Chat con IA</h2>
    <v-list class="mb-4">
      <v-list-item
        v-for="(msg, index) in messages"
        :key="index"
      >
        <v-list-item-content>
          <v-list-item-title class="text-subtitle-1">
            {{ msg.from }}:
          </v-list-item-title>
          <v-list-item-subtitle>{{ msg.text }}</v-list-item-subtitle>
        </v-list-item-content>
      </v-list-item>
    </v-list>
    <v-text-field
      v-model="input"
      label="Escribe tu mensaje"
      append-icon="mdi-send"
      @click:append="send"
    />
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Message {
  from: string
  text: string
}

const messages = ref<Message[]>([
  { from: 'AI', text: 'Hola, ¿en qué puedo ayudarte?' },
])

const input = ref('')

function send () {
  if (!input.value) return
  messages.value.push({ from: 'Tú', text: input.value })
  messages.value.push({
    from: 'AI',
    text: 'Esta es una respuesta generada de forma simulada.',
  })
  input.value = ''
}
</script>

<route lang="yaml">
meta:
  requiresAuth: true
</route>
