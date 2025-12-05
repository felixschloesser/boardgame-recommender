<script lang="ts" setup>
import { RouterLink } from 'vue-router'
import { onMounted, ref } from 'vue'
import GameAdder from '@/components/GameAdder.vue'
import type { Option } from '@/boardGame.mjs'
import * as api from '@/api.mjs'
import type BoardGame from '@/boardGame.mjs'

interface Props {
  id?: string // id can be undefined if not passed as a prop
}

const props = defineProps<Props>()

const games = ref<Option[]>([])

onMounted(async () => {
  const gameObj: BoardGame[] = await api.getGames()
  const gamesToAdd = gameObj.map((game) => ({
    id: game.id,
    name: game.title,
  }))
  games.value.push(...gamesToAdd)
})

const addedGames = ref<InstanceType<typeof GameAdder> | null>(null)
const playerCount = ref(4)

const confirm = () => {
  if (addedGames.value) console.log(addedGames.value.getGames())
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><img src="../assets/home.svg" alt="Home" class="icon" /></RouterLink
    ><RouterLink to="/wishlist"
      ><img src="../assets/wishlist.svg" alt="Wishlist" class="icon"
    /></RouterLink>
  </nav>
  <h1>Enter games you already tried and liked here:</h1>
  <GameAdder ref="addedGames" :options="games" :id="props.id" />
  <h1>Enter preferred number of players:</h1>
  <input type="number" min="1" v-model="playerCount" />
  <button @click="confirm">Get Recommendations</button>
</template>
