<template>
  <v-container class="fill-height d-flex align-center justify-center">
    <v-card
      class="pa-8 text-center"
      min-width="400px"
      elevation="12"
      rounded="xl"
      v-bind:class="{ 'scale-fade': navigating }"
    >
      <h1 class="text-h4 font-weight-bold mb-2">PLATINO</h1>

      <v-btn color="indigo" variant="flat" size="small" @click="startChat">
        Comenzar chat
        <v-icon end>mdi-arrow-right</v-icon>
      </v-btn>

      <v-img :src="uditLogo" class="my-4 mx-auto rounded" width="150px" />
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import uditLogo from "@/assets/images/UDIT_LOGOTIPO_LATERAL_Negativo.png";
const navigating = ref(false);
const router = useRouter();

const startChat = () => {
  navigating.value = true;
  setTimeout(() => {
    router.push("dashboard/chat");
  }, 600); // tiempo para que se vea la animación
};
</script>

<style scoped>
.scale-fade {
  animation: zoomOut 0.6s ease-in-out forwards;
}

@keyframes zoomOut {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(1.1);
  }
}
</style>
