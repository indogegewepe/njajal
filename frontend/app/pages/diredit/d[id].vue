<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import useApi from '~/composables/useApi'

const router = useRouter()
const route = useRoute()
const { id } = route.params
const toast = useToast()
const { fetchData, sendData } = useApi()

const form = ref({
  id_dosen: null,
  nama_dosen: ''
})

const isLoading = ref(true)
const isSubmitting = ref(false)

onMounted(async () => {
  try {
    const data = await fetchData(`dosen/${id}`)
    form.value = {
      id_dosen: id,
      nama_dosen: data.nama_dosen
    }
  } catch (error) {
    toast.add({
      title: 'Gagal',
      message: 'Terjadi kesalahan: ' + error,
      icon: 'i-lucide-close-circle',
      duration: 5000,
      color: 'error'
    })
  } finally {
    isLoading.value = false
  }
})

const goToEdit = (type) => {
  router.push({ path: '/edit', query: { type } })
}

const ToastBerhasil = (message) => {
  toast.add({
    title: 'Berhasil',
    message: message,
    icon: 'i-lucide-check-circle',
    duration: 5000,
    color: 'success'
  })
}

const handleSubmit = async () => {
  try {
    isSubmitting.value = true
    const payload = {
      id_dosen: parseInt(id),
      nama_dosen: form.value.nama_dosen
    }
    await sendData(`dosen/${id}`, 'PUT', payload)
    ToastBerhasil('Data dosen berhasil diperbarui')
    goToEdit('dosen')
  } catch (error) {
    toast.add({
      title: 'Gagal',
      message: 'Terjadi kesalahan: ' + error,
      icon: 'i-lucide-close-circle',
      duration: 5000,
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="p-4">
    <UCard variant="soft">
      <template #header>
        <h2 class="text-2xl font-bold">Edit Dosen</h2>
      </template>

      <form @submit.prevent="handleSubmit">
        <div class="space-y-4">
          <label for="id_dosen">ID Dosen</label>
          <UInput id="id_dosen" v-model="id" class="w-full" disabled />

          <label for="nama_dosen">Nama Dosen</label>
          <UInput 
            id="nama_dosen" 
            v-model="form.nama_dosen" 
            class="w-full"
            placeholder="Contoh: Adhi Prahara, S.Si., M.Cs."
            required 
          />
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <UButton type="button" label="Batal" color="error" @click="goToEdit('dosen')" />
          <UButton type="submit" label="Simpan Perubahan" :loading="isSubmitting" />
        </div>
      </form>
    </UCard>
  </div>
</template>