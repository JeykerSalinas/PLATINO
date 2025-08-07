<template>
  <div class="loading-dots text-error">
    <span class="bg-grey"></span>
    <span class="bg-grey"></span>
    <span class="bg-grey"></span>
  </div>
</template>
<style lang="scss" scoped>
.loading-dots {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  height: 24px;
  width: 48px;;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  animation: bounce 0.8s infinite ease-in-out;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-6px);
  }
}
</style>
