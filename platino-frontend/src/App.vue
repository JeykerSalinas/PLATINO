<template>
  <v-layout class="rounded rounded-md border fill-height bg-background">
    <RouterView />
    <NotificationSnackbar />
  </v-layout>
</template>

<script lang="ts" setup>
import NotificationSnackbar from "./components/NotificationSnackbar.vue";
import { onMounted } from "vue";
import { useTheme } from "vuetify";

onMounted(() => {
  if (!localStorage.getItem("platino-theme")) {
    useTheme().global.name.value = "light";
    localStorage.setItem("platino-theme", "light");
  } else {
    useTheme().global.name.value =
      localStorage.getItem("platino-theme") ?? "light";
  }
});
</script>
<style lang="scss">
#app {
  height: 100vh;
}
</style>
