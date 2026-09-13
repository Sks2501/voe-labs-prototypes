plugins {
    id("com.android.application")
}

android {
    namespace = "com.grin.iotinspector"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.grin.iotinspector"
        minSdk = 26
        targetSdk = 37
        versionCode = 3
        versionName = "1.2.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
