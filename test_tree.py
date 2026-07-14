import sys
import os
import asyncio
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from src.server.app import (
    get_artifacts_tree,
    rename_artifact, RenameArtifactRequest,
    move_to_folder, MoveToFolderRequest,
    create_artifact, CreateArtifactRequest,
    delete_artifact, DeleteArtifactRequest
)

# Retrieve the actual module object from sys.modules to avoid package shadowing
app_mod = sys.modules['src.server.app']

async def run_tests():
    print("app_mod type:", type(app_mod))
    print("Initial cache state:", app_mod._artifacts_tree_cache)

    print("\n=== Test 1: First invocation (Should hit disk) ===")
    start_time = time.time()
    res1 = await get_artifacts_tree()
    elapsed1 = time.time() - start_time
    print(f"First call: Status={res1.get('status')}, Elapsed={elapsed1:.6f} seconds")
    print("Cache after first call:", app_mod._artifacts_tree_cache is not None)
    
    print("\n=== Test 2: Second invocation within TTL (Should hit Cache) ===")
    start_time = time.time()
    res2 = await get_artifacts_tree()
    elapsed2 = time.time() - start_time
    print(f"Second call: Status={res2.get('status')}, Elapsed={elapsed2:.6f} seconds")
    print("Cache after second call:", app_mod._artifacts_tree_cache is not None)
    assert elapsed2 < elapsed1 or elapsed2 < 0.002, "Second call did not hit cache!"
    
    print("\n=== Test 3: Third invocation after 2s TTL (Should hit disk again) ===")
    print("Sleeping for 2.2 seconds...")
    await asyncio.sleep(2.2)
    start_time = time.time()
    res3 = await get_artifacts_tree()
    elapsed3 = time.time() - start_time
    print(f"Third call: Status={res3.get('status')}, Elapsed={elapsed3:.6f} seconds")
    print("Cache after third call:", app_mod._artifacts_tree_cache is not None)
    
    print("\n=== Test 4: Cache invalidation check ===")
    # Fill cache
    await get_artifacts_tree()
    print("Cache before manual invalidate:", app_mod._artifacts_tree_cache is not None)
    app_mod._artifacts_tree_cache = None
    print("Cache after manual invalidate:", app_mod._artifacts_tree_cache is not None)
    
    start_time = time.time()
    res4 = await get_artifacts_tree()
    elapsed4 = time.time() - start_time
    print(f"Call after cache invalidation: Status={res4.get('status')}, Elapsed={elapsed4:.6f} seconds")
    print("Cache after invalidation call:", app_mod._artifacts_tree_cache is not None)
    
    print("\n=== Test 5: Modifying endpoints invalidation check ===")
    
    # 5.1 Rename
    print("Running get_artifacts_tree to fill cache for rename test...")
    await get_artifacts_tree()
    print("Cache state before rename:", app_mod._artifacts_tree_cache is not None)
    with patch('os.rename') as mock_rename, patch('os.path.exists', return_value=True):
        req = RenameArtifactRequest(old_path="C:/github/obsidian-vault/_cobalt/Reports/2026-06-26/somefile.md", new_name="newfile.md")
        await rename_artifact(req)
    print("Cache state after rename:", app_mod._artifacts_tree_cache is not None)
    assert app_mod._artifacts_tree_cache is None, "Rename did not invalidate cache!"
    print("  - Rename invalidation: PASSED")
    
    # 5.2 Move
    await get_artifacts_tree()
    assert app_mod._artifacts_tree_cache is not None
    def exists_side_effect(path):
        normalized = path.replace("\\", "/").lower()
        if "somefile.md" in normalized and "notes" not in normalized:
            return True
        return False
        
    with patch('shutil.move') as mock_move, patch('os.path.exists', side_effect=exists_side_effect), patch('os.makedirs'):
        req = MoveToFolderRequest(source_path="C:/github/obsidian-vault/_cobalt/Reports/2026-06-26/somefile.md", target_folder="Notes")
        await move_to_folder(req)
    assert app_mod._artifacts_tree_cache is None, "Move did not invalidate cache!"
    print("  - Move invalidation: PASSED")
    
    # 5.3 Create
    await get_artifacts_tree()
    assert app_mod._artifacts_tree_cache is not None
    with patch('builtins.open') as mock_open, patch('os.path.exists', return_value=False), patch('os.makedirs'):
        req = CreateArtifactRequest(folder="2026-06-26")
        await create_artifact(req)
    assert app_mod._artifacts_tree_cache is None, "Create did not invalidate cache!"
    print("  - Create invalidation: PASSED")
    
    # 5.4 Delete
    await get_artifacts_tree()
    assert app_mod._artifacts_tree_cache is not None
    with patch('os.remove') as mock_remove, patch('os.path.exists', return_value=True):
        req = DeleteArtifactRequest(path="C:/github/obsidian-vault/_cobalt/Reports/2026-06-26/somefile.md")
        await delete_artifact(req)
    assert app_mod._artifacts_tree_cache is None, "Delete did not invalidate cache!"
    print("  - Delete invalidation: PASSED")
    
    print("\n=== All Cache and Invalidation Verifications SUCCESSFUL ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
