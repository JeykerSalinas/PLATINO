<template>
  <v-snackbar v-model="store.show" :color="store.color" multi-line>
    {{ store.message }}
  </v-snackbar>
</template>

<script setup lang="ts">
import { useNotificationStore } from '@/stores/notifications'
const store = useNotificationStore()
</script>
