<script setup lang="ts">
// todo fetch study group & session info from backend
</script>

<template>
  <main>
    <RouterView v-slot="{ Component }">
      <component :is="Component" explanationStyle="analogy" />
    </RouterView>
  </main>
</template>

<!-- Global styles --->
<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100vh;
}

.icon {
  width: 35px;
  height: 35px;
  padding: 10px;
  cursor: pointer;
}

.navbar {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
</style>
