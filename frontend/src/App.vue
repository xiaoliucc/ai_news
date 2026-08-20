<script setup lang="ts">
// Element Plus 中文 locale（组件按需自动导入，此处仅注入语言配置）
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>
