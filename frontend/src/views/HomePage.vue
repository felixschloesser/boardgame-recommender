<script lang="ts" setup>
import { RouterLink } from 'vue-router'
import { getWishlist } from '@/wishlist.mjs'
</script>

<template>
  <div class="center">
    <h1>Boardgame Recommender</h1>
    <div>
      <div>
        <RouterLink to="/wishlist" v-if="getWishlist().length > 0"
          ><div><button class="nav-button"><img src="../assets/wishlist.svg" alt="wishlist" class="small-icon" /> Wishlist</button></div></RouterLink
        >
      </div>
      <div>
        <RouterLink to="/explore"><div><button class="nav-button"><img src="../assets/explore.svg" alt="Explore" class="small-icon" /> Explore</button></div></RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nav-button {
  background-color: lightblue;
  border: 1px solid #000;
  border-radius: 8px;
  margin: 10px;
  padding: 6px 10px;
  min-width: 120px;
  height: 36px;
  display: inline-flex;
  flex-direction: row;
  align-items: center; /* vertically center icon + text */
  justify-content: center;
  gap: 8px; /* space between icon and text */
  font-size: 20px;
  font-weight: 700;
  color: #000;
  cursor: pointer;
}


a { text-decoration: none; }


.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100vh;
}
</style>
