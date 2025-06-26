<template>
  <v-btn class="mt-4" @click="login">Iniciar sesión</v-btn>
  <div class="mt-2">
    <RouterLink to="/dashboard">Ir al Dashboard</RouterLink>
  </div>
</template>

<script setup lang="ts">
function login() {
  localStorage.setItem("auth", "true");
}
</script>
