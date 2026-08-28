/**
 * A bifurcacao do Live.
 *
 * Duas zonas, dois enderecos:
 *
 * - `/`     vitrine e demonstracoes, para quem esta avaliando;
 * - `/app`  o produto, para quem ja e cliente.
 *
 * Antes era uma pagina so. O produto entrava como a ultima secao da vitrine,
 * abaixo do catalogo, do painel de upload, do terminal e dos artefatos — e
 * portanto abaixo de tudo que ele nao e.
 */

import Produto from "./Produto";
import Vitrine from "./Vitrine";
import { ehDoProduto, useCaminho } from "./lib/rotas";

export default function App() {
  return ehDoProduto(useCaminho()) ? <Produto /> : <Vitrine />;
}
