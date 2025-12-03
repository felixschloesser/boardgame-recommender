<script lang="ts" setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="center">
    <h1>Boardgame Recommender</h1>
    <div>
      <div>
        <RouterLink to="/wishlist"><button class="nav-button">Wishlist</button></RouterLink>
      </div>
      <div>
        <RouterLink to="/explore"><button class="nav-button">Explore</button></RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nav-button {
  background-color: lightblue;
  border: black 1px solid;
  border-radius: 8px;
  margin: 10px;
  padding: 4px;
  width: 100px;
  text-align: center;
  font-size: large;
  font-weight: bold;
  color: black;
  cursor: pointer;
}

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100vh;
}
</style>
