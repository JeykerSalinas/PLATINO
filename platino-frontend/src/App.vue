<template>
  <v-layout class="rounded rounded-md border fill-height">
    <RouterView />
    <NotificationSnackbar />
  </v-layout>
</template>

<script lang="ts" setup>
import NotificationSnackbar from './components/NotificationSnackbar.vue'
</script>
<style lang="scss">
#app {
  height: 100vh;
}
</style>
