/* A deliberately small, escaped Markdown renderer. No raw HTML is accepted. */
(function(root){
  function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function inline(source){
    const tokens=[];const put=html=>'\u0000'+(tokens.push(html)-1)+'\u0000';
    let s=String(source).replace(/\u0000/g,'');
    s=s.replace(/`([^`]+)`/g,(_,v)=>put('<code>'+esc(v)+'</code>'));
    s=s.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g,(_,label,url)=>{
      try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol))return label;}catch{return label;}
      return put('<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+'</a>');
    });
    s=esc(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/__([^_]+)__/g,'<strong>$1</strong>').replace(/~~([^~]+)~~/g,'<del>$1</del>').replace(/(^|\s)\*([^*\n]+)\*(?=\s|[，。！？,.!?]|$)/g,'$1<em>$2</em>');
    return s.replace(/\u0000(\d+)\u0000/g,(_,i)=>tokens[Number(i)]||'');
  }
  function render(source){
    const lines=String(source??'').replace(/\r/g,'').split('\n');const out=[];let paragraph=[],list=null,code=null;
    const flush=()=>{if(paragraph.length){out.push('<p>'+inline(paragraph.join(' ').trim())+'</p>');paragraph=[];}};
    const closeList=()=>{if(list){out.push('</'+list+'>');list=null;}};
    for(let i=0;i<lines.length;i++){
      const line=lines[i].trim();
      if(line.startsWith('```')){flush();closeList();if(code!==null){out.push('<pre><code>'+esc(code.join('\n'))+'</code></pre>');code=null;}else code=[];continue;}
      if(code!==null){code.push(lines[i]);continue;}
      if(!line){flush();closeList();continue;}
      if(/^\|?.+\|.+\|?$/.test(line)&&i+1<lines.length&&/^\|?\s*:?-{3,}/.test(lines[i+1].trim())){
        flush();closeList();const cells=x=>x.replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
        out.push('<div class="table-scroll"><table><thead><tr>'+cells(line).map(v=>'<th>'+inline(v)+'</th>').join('')+'</tr></thead><tbody>');i++;
        while(i+1<lines.length&&lines[i+1].includes('|')&&lines[i+1].trim()){i++;out.push('<tr>'+cells(lines[i].trim()).map(v=>'<td>'+inline(v)+'</td>').join('')+'</tr>');}
        out.push('</tbody></table></div>');continue;
      }
      const heading=line.match(/^(#{1,6})\s+(.+)$/);
      if(heading){flush();closeList();const n=Math.min(4,heading[1].length+1);out.push('<h'+n+'>'+inline(heading[2])+'</h'+n+'>');continue;}
      const plain=line.replace(/^\*\*|\*\*$/g,'');
      if((/^[一二三四五六七八九十]+、/.test(plain)||/^（[一二三四五六七八九十]+）/.test(plain))&&plain.length<65){flush();closeList();const n=plain.startsWith('（')?4:3;out.push('<h'+n+'>'+inline(plain)+'</h'+n+'>');continue;}
      const li=line.match(/^(?:[-*+]\s+|\d+[.)、]\s+)(.+)$/);
      if(li){flush();const tag=/^\d/.test(line)?'ol':'ul';if(list!==tag){closeList();out.push('<'+tag+'>');list=tag;}out.push('<li>'+inline(li[1])+'</li>');continue;}
      if(/^>\s?/.test(line)){flush();closeList();out.push('<blockquote>'+inline(line.replace(/^>\s?/,''))+'</blockquote>');continue;}
      if(/^([-*_])\1{2,}$/.test(line)){flush();closeList();out.push('<hr>');continue;}
      closeList();paragraph.push(line);
    }
    flush();closeList();if(code!==null)out.push('<pre><code>'+esc(code.join('\n'))+'</code></pre>');return out.join('');
  }
  const api={esc,inline,render};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.YuewenFormat=api;
})(typeof window!=='undefined'?window:{});
