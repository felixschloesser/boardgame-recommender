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
</style>
