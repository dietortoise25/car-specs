import json
import os
from googletrans import Translator
from typing import Dict, List, Any
import time
from shutil import copy2

class SpecExporter:
    def __init__(self):
        self.translator = Translator()
        self.data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                     "GROUP/merged_data_20241205_161556.json")
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache = self._load_cache()
        self.spec_data_cache = {}
    
    def _load_cache(self) -> Dict[str, Dict[str, str]]:
        """加载翻译缓存"""
        cache_file = os.path.join(self.cache_dir, "translation_cache.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载缓存出错: {e}")
        return {}
    
    def _save_cache(self):
        """保存翻译缓存"""
        cache_file = os.path.join(self.cache_dir, "translation_cache.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存出错: {e}")
    
    def load_spec_data(self, spec_id: str) -> Dict[str, Any]:
        """加载指定车型的数据（带缓存）"""
        if spec_id in self.spec_data_cache:
            return self.spec_data_cache[spec_id]
            
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for brand_name, brand_data in data.items():
                if not isinstance(brand_data, dict):
                    continue
                    
                if 'series' in brand_data:
                    for series_name, series_data in brand_data['series'].items():
                        if not isinstance(series_data, dict):
                            continue
                            
                        if 'models' in series_data:
                            for model_name, model_data in series_data['models'].items():
                                if not isinstance(model_data, dict):
                                    continue
                                    
                                if str(model_data.get('spec_id')) == spec_id:
                                    spec_data = {
                                        'specId': model_data.get('spec_id'),
                                        'specName': model_name,
                                        'brandName': brand_name,
                                        'seriesName': series_name,
                                        'manufacturerName': brand_data.get('manufacturer_name', 'N/A'),
                                        'yearType': model_name.split('款')[0] if '款' in model_name else 'N/A',
                                        'price': model_data.get('price', 'N/A'),
                                    }
                                    
                                    if 'config_data' in model_data:
                                        param_values = []
                                        for category, params in model_data['config_data'].items():
                                            for param_name, param_value in params.items():
                                                param_values.append({
                                                    'name': f"{category}-{param_name}",
                                                    'value': str(param_value)
                                                })
                                        spec_data['paramValues'] = param_values
                                    
                                    self.spec_data_cache[spec_id] = spec_data
                                    return spec_data
            
            return None
            
        except Exception as e:
            print(f"读取数据时出错: {str(e)}")
            return None

    def translate_text(self, text: str, dest_lang: str, max_retries: int = 3, retry_delay: int = 1) -> str:
        """带缓存和重试机制的翻译"""
        if not text or text == 'N/A':
            return text
            
        cache_key = f"{text}_{dest_lang}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(retry_delay)
                result = self.translator.translate(text, dest=dest_lang)
                translated = result.text
                self.cache[cache_key] = translated
                self._save_cache()
                return translated
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"翻译出错 ({text}): {e}")
                    return text
                continue

    def batch_translate(self, texts: List[str], dest_lang: str) -> List[str]:
        """批量翻译，使用缓存"""
        return [self.translate_text(text, dest_lang) for text in texts]

    def export_spec_info(self, spec_id: str):
        """导出单个车型的HTML文件"""
        spec_data = self.load_spec_data(spec_id)
        if not spec_data:
            return
        
        # 修改翻译数据的组织方式
        polish_info = {'基本信息': []}  # 使用字典存储不同类型的参数
        try:
            # 翻译基本信息
            base_items = ['车型名称', '品牌', '厂商', '车系', '年款', '价格(万)', '车型ID']
            base_values = [
                spec_data.get('specName', 'N/A'),
                spec_data.get('brandName', 'N/A'),
                spec_data.get('manufacturerName', 'N/A'),
                spec_data.get('seriesName', 'N/A'),
                spec_data.get('yearType', 'N/A'),
                spec_data.get('price', 'N/A'),
                spec_data.get('specId', 'N/A')
            ]
            
            items_pl = self.batch_translate(base_items, 'pl')
            values_pl = self.batch_translate([str(v) for v in base_values], 'pl')
            polish_info['基本信息'] = list(zip(items_pl, values_pl))
            
            # 处理配置信息，按类型分组
            if 'paramValues' in spec_data:
                for param in spec_data['paramValues']:
                    param_type, param_name = param['name'].split('-', 1)
                    if param_type not in polish_info:
                        polish_info[param_type] = []
                    
                    # 翻译参数名和值
                    name_pl = self.translate_text(param_name, 'pl')
                    value_pl = self.translate_text(param['value'], 'pl')
                    polish_info[param_type].append((name_pl, value_pl))
        except Exception as e:
            print(f"翻译出错: {e}")
            return
        
        # 处理图片
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 "docs", f"spec_{spec_id}")
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        # 直接从images目录获取图片
        car_images = []
        if os.path.exists(images_dir):
            for file in os.listdir(images_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    car_images.append(file)
            
            # 按数字顺序排序图片
            car_images.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
            print(f"从 {images_dir} 找到 {len(car_images)} 张图片")
        else:
            print(f"警告: 图片目录不存在 {images_dir}")
        
        # 修改HTML模板，添加折叠功能
        table_html = ""
        for category, params in polish_info.items():
            category_pl = self.translate_text(category, 'pl')
            category_id = f"category_{hash(category) & 0xFFFFFFFF}"  # 创建唯一ID
            
            table_html += f"""
            <div class="card mb-3">
                <div class="card-header" id="header_{category_id}">
                    <h5 class="mb-0">
                        <button class="btn btn-link" type="button" data-bs-toggle="collapse" 
                                data-bs-target="#collapse_{category_id}" aria-expanded="true">
                            {category_pl}
                        </button>
                    </h5>
                </div>
                <div id="collapse_{category_id}" class="collapse show">
                    <div class="card-body p-0">
                        <table class="table mb-0">
                            <tbody>
                                {"".join(f'<tr><td style="width: 50%">{name}</td><td style="width: 50%">{value}</td></tr>' for name, value in params)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            """
        
        # 修改HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Specyfikacja pojazdu {spec_id}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                :root {{
                    --primary-color: #2c3e50;
                    --secondary-color: #34495e;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8f9fa;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 2rem auto;
                }}
                .title {{
                    text-align: center;
                    margin-bottom: 2rem;
                    padding: 1rem;
                    background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
                    color: white;
                    border-radius: 10px;
                }}
                .carousel {{
                    margin-bottom: 2rem;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    border-radius: 10px;
                    overflow: hidden;
                }}
                .carousel-item img {{
                    width: 100%;
                    height: 600px;
                    object-fit: contain;
                    background-color: black;
                }}
                .spec-table {{
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
                .table th {{
                    background-color: var(--secondary-color);
                    color: white;
                    padding: 1rem;
                }}
                .table td {{
                    padding: 1rem;
                    word-break: break-word;
                }}
                .card-header {{
                    background: var(--secondary-color);
                    padding: 0;
                }}
                .btn-link {{
                    color: white;
                    text-decoration: none;
                    width: 100%;
                    text-align: left;
                    padding: 1rem;
                }}
                .btn-link:hover {{
                    color: #f8f9fa;
                    text-decoration: none;
                }}
                .card {{
                    border: none;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
                .table {{
                    margin-bottom: 0;
                }}
                .collapse {{
                    border-top: 1px solid rgba(0,0,0,0.125);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">
                    <h1>Specyfikacja pojazdu</h1>
                    <h3>{spec_data.get("brandName", "N/A")} {spec_data.get("seriesName", "N/A")}</h3>
                    <h4>{spec_data.get("specName", "N/A")}</h4>
                </div>
                
                <div id="carCarousel" class="carousel slide" data-bs-ride="carousel">
                    <div class="carousel-indicators">
                        {"".join(f'<button type="button" data-bs-target="#carCarousel" data-bs-slide-to="{i}" {"class=active" if i==0 else ""}></button>' for i in range(len(car_images)))}
                    </div>
                    <div class="carousel-inner">
                        {"".join(f'<div class="carousel-item {"active" if i==0 else ""}"><img src="images/{img}" class="d-block w-100" alt="Car Image {i+1}"></div>' for i, img in enumerate(car_images))}
                    </div>
                    <button class="carousel-control-prev" type="button" data-bs-target="#carCarousel" data-bs-slide="prev">
                        <span class="carousel-control-prev-icon"></span>
                    </button>
                    <button class="carousel-control-next" type="button" data-bs-target="#carCarousel" data-bs-slide="next">
                        <span class="carousel-control-next-icon"></span>
                    </button>
                </div>
                
                <div class="spec-tables">
                    {table_html}
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    // 轮播初始化
                    var carousel = new bootstrap.Carousel(document.getElementById('carCarousel'), {{
                        interval: 3000,
                        wrap: true
                    }});
                    
                    // 添加折叠按钮图标
                    document.querySelectorAll('.btn-link').forEach(btn => {{
                        btn.innerHTML += '<i class="float-end">▼</i>';
                        btn.addEventListener('click', function() {{
                            const icon = this.querySelector('i');
                            icon.style.transform = this.getAttribute('aria-expanded') === 'true' 
                                ? 'rotate(180deg)' 
                                : 'rotate(0deg)';
                        }});
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        # 保存HTML文件
        output_path = os.path.join(output_dir, "index.html")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n波兰语HTML已导出到: {output_dir}/index.html")
        print(f"图片目录: {images_dir}")
        print(f"图片列表: {car_images}")

    def export_index_html(self, specs: List[Dict]):
        """生成索引页面"""
        specs_html = ""
        for spec in specs:
            specs_html += f"""
            <div class="col-md-4 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <h5 class="card-title">{spec['brandName']} {spec['seriesName']}</h5>
                        <p class="card-text">{spec['specName']}</p>
                        <a href="spec_{spec['specId']}/index.html" class="btn btn-primary">查看详情</a>
                    </div>
                </div>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>车型规格信息</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                :root {{
                    --primary-color: #2c3e50;
                    --secondary-color: #34495e;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8f9fa;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 2rem auto;
                }}
                .title {{
                    text-align: center;
                    margin-bottom: 2rem;
                    padding: 1rem;
                    background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
                    color: white;
                    border-radius: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">
                    <h1>车型规格信息</h1>
                </div>
                
                <div class="row">
                    {specs_html}
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """
        
        # 保存到 docs 目录（GitHub Pages 默认目录）
        os.makedirs('docs', exist_ok=True)
        with open('docs/index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

    def export_all_specs(self):
        """导出所有车型信息"""
        specs = []
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for brand_name, brand_data in data.items():
                if not isinstance(brand_data, dict):
                    continue
                    
                if 'series' in brand_data:
                    for series_name, series_data in brand_data['series'].items():
                        if not isinstance(series_data, dict):
                            continue
                            
                        if 'models' in series_data:
                            for model_name, model_data in series_data['models'].items():
                                if not isinstance(model_data, dict):
                                    continue
                            
                            spec_id = str(model_data.get('spec_id'))
                            if spec_id:
                                specs.append({
                                    'specId': spec_id,
                                    'specName': model_name,
                                    'brandName': brand_name,
                                    'seriesName': series_name
                                })
                                self.export_spec_info(spec_id)
                                print(f"已导出车型: {brand_name} {series_name} {model_name}")
        
            # 生成索引页
            self.export_index_html(specs)
            print("已生成索引页")
            
        except Exception as e:
            print(f"导出过程出错: {e}")

def main():
    exporter = SpecExporter()
    # 导出所有车型
    exporter.export_all_specs()

if __name__ == "__main__":
    main() 