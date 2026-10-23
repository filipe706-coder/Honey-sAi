package pt.filipe.sussurros

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

// Estas classes têm os mesmos nomes de campos que o servidor (main.py).
// O Gson converte-as automaticamente de/para JSON.
data class Mensagem(val papel: String, val texto: String) // papel: "utilizador" ou "personagem"
data class PedidoChat(val mensagens: List<Mensagem>)
data class RespostaChat(val resposta: String)

// O Retrofit lê esta interface e cria o código que faz o pedido HTTP.
// "suspend" = a função espera pela resposta sem bloquear o ecrã.
interface SussurrosApi {
    @POST("chat")
    suspend fun enviar(@Body pedido: PedidoChat): RespostaChat
}

object Servidor {
    // No EMULADOR, 10.0.2.2 é o endereço do teu PC.
    // Num TELEMÓVEL a sério, troca pelo IP do PC na tua rede Wi-Fi
    // (ex: "http://192.168.1.50:8000/"). Ver README.
    private const val URL_BASE = "http://10.0.2.2:8000/"

    // A IA pode demorar uns segundos, por isso damos até 60s de espera.
    private val http = OkHttpClient.Builder()
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    val api: SussurrosApi = Retrofit.Builder()
        .baseUrl(URL_BASE)
        .client(http)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(SussurrosApi::class.java)
}
