<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Participant } from './api.mts'
import * as api from './api.mts'

const participant = ref(null as Participant | null)

// todo fetch study group & session info from backend
onMounted(async () => {
  // check if participant ID exists in local storage
  const storedParticipantId = localStorage.getItem('participant_id')
  if (storedParticipantId) {
    participant.value = { participant_id: storedParticipantId }
    console.log('Existing participant ID:', storedParticipantId)
  } else {
    // create new participant
    participant.value = await api.newParticipant().then((participant) => {
      console.log('New participant ID:', participant.participant_id)
      return participant
    })
    // store participant ID in local storage
    if (participant.value) localStorage.setItem('participant_id', participant.value.participant_id)
  }
})
</script>

<template>
  <main class="container">
    <RouterView v-slot="{ Component }">
      <component :is="Component" explanationStyle="analogy" />
    </RouterView>
  </main>
  
</template>

<!-- Keep this file free of app-specific global CSS; theme is in styles/theme.css -->
<style>
</style>
