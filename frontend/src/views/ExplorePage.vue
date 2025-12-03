<script lang="ts" setup>
import { RouterLink } from 'vue-router'
import { ref } from 'vue'
import GameAdder from '@/components/GameAdder.vue'

const exampleOptions = [
  { id: '1', name: 'Catan' },
  { id: '2', name: 'Pandemic' },
  { id: '3', name: 'Ticket to Ride' },
  { id: '4', name: 'Carcassonne' },
  { id: '5', name: '7 Wonders' },
  { id: '6', name: 'Dominion' },
  { id: '7', name: 'Azul' },
  { id: '8', name: 'Splendor' },
  { id: '9', name: 'Terraforming Mars' },
  { id: '10', name: 'Wingspan' },
  { id: '11', name: 'Gloomhaven' },
]

const addedGames = ref<InstanceType<typeof GameAdder> | null>(null)
const playerCount = ref(4)

const confirm = () => {
  if (addedGames.value) console.log(addedGames.value.getGames())
}
</script>

<template>
  <nav>
    <RouterLink to="/"><div>Home</div></RouterLink
    ><RouterLink to="/wishlist"><div>Wishlist</div></RouterLink>
  </nav>
  <h1>Enter games you already tried and liked here:</h1>
  <GameAdder ref="addedGames" :options="exampleOptions" />
  <h1>Enter preferred number of players:</h1>
  <input type="number" min="1" v-model="playerCount" />
  <button @click="confirm">Get Recommendations</button>
</template>
