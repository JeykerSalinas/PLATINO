<template>
  <div>
    <h1>Dashboard</h1>
    <nav class="mb-4">
      <RouterLink to="/dashboard/chat">Chat</RouterLink>
      |
      <RouterLink to="/dashboard/stats">Stats</RouterLink>
    </nav>
    <router-view />
  </div>
</template>

<script setup lang="ts">
//
</script>

<route lang="yaml">
meta:
  requiresAuth: true
</route>
