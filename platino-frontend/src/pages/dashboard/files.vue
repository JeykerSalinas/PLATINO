<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <h3 class="text-h6 mb-4">Subir archivo</h3>
          <v-file-input
            label="Selecciona archivo"
            @change="handleFileUpload"
            prepend-icon="mdi-upload"
            show-size
          />
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <h3 class="text-h6 mb-4">Archivos subidos</h3>
          <v-list v-if="files.length">
            <v-list-item
              v-for="(file, index) in files"
              :key="index"
            >
              <v-list-item-content>
                <v-list-item-title>{{ file.name }}</v-list-item-title>
                <v-list-item-subtitle>{{ file.size }} bytes - {{ file.type }}</v-list-item-subtitle>
              </v-list-item-content>
              <v-list-item-action>
                <v-icon color="red" @click="removeFile(index)">mdi-delete</v-icon>
              </v-list-item-action>
            </v-list-item>
          </v-list>
          <div v-else class="text-medium-emphasis">No hay archivos aún</div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const files = ref<File[]>([])

function handleFileUpload(newFile: File | File[]) {
  if (!newFile) return
  const selected = Array.isArray(newFile) ? newFile : [newFile]
  files.value.push(...selected)
}

function removeFile(index: number) {
  files.value.splice(index, 1)
}
</script>
